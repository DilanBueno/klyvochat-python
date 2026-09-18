from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from client.storage.database import Base
from client.storage.repositories import SettingsRepository
from client.ui.theme import ThemeManager


def make_settings_repo() -> SettingsRepository:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session() -> Iterator[Any]:
        session = session_maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return SettingsRepository(session_factory=_session)


@pytest.fixture(scope="session")
def qapp() -> Any:
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_settings_repository_roundtrip() -> None:
    repo = make_settings_repo()
    assert repo.get("chat_font_size") is None
    repo.set("chat_font_size", "15")
    assert repo.get("chat_font_size") == "15"
    assert repo.get("missing", "fallback") == "fallback"
    repo.set("chat_font_size", "16")
    assert repo.get("chat_font_size") == "16"
    assert repo.get_all() == {"chat_font_size": "16"}


def test_theme_manager_dark_light_accent() -> None:
    manager = ThemeManager()
    manager.set_theme("dark")
    assert manager.get_color("bg_primary") == "#1b2838"
    manager.set_theme("light")
    assert manager.get_color("bg_primary") == "#eef1f5"
    assert manager.get_color("text_primary") == "#1b2838"
    manager.set_accent("#ff0000")
    assert manager.get_color("accent") == "#ff0000"
    assert manager.get_color("accent_hover") == "#ff0000"
    with pytest.raises(ValueError):
        manager.set_theme("purple")
    manager.set_theme("dark")
    manager.set_accent(None)


def test_settings_window_persists_and_signals(qapp) -> None:
    from client.ui.windows.settings_window import (
        SETTING_AUTO_ACCEPT,
        SETTING_THEME,
        SettingsWindow,
    )

    repo = make_settings_repo()
    window = SettingsWindow(settings_repo=repo, current_user=None, audio_stream=None)

    received: list[bool] = []
    window.auto_accept_changed.connect(received.append)
    window.auto_accept_check.setChecked(True)
    assert received == [True]
    assert repo.get(SETTING_AUTO_ACCEPT) == "1"

    themes: list[str] = []
    window.theme_changed.connect(themes.append)
    window.light_radio.setChecked(True)
    assert themes == ["light"]
    assert repo.get(SETTING_THEME) == "light"

    window.close()


def test_chat_input_send_enter_behavior(qapp) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    from client.ui.windows.chat_window import ChatInput

    sent: list[bool] = []

    enter = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Return, Qt.KeyboardModifier.NoModifier)

    input_enter = ChatInput(send_enter=True)
    input_enter.submit.connect(lambda: sent.append(True))
    input_enter.keyPressEvent(enter)
    assert sent == [True]

    ctrl_enter = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key_Return,
        Qt.KeyboardModifier.ControlModifier,
    )
    input_ctrl = ChatInput(send_enter=False)
    input_ctrl.submit.connect(lambda: sent.append(True))
    input_ctrl.keyPressEvent(enter)
    assert sent == [True]
    input_ctrl.keyPressEvent(ctrl_enter)
    assert sent == [True, True]
