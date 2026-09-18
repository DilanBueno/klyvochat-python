from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from client.core.notification_manager import NotificationManager
from client.storage.database import Base
from client.storage.models import Message
from client.storage.repositories import MessageRepository, SettingsRepository


def make_session_factory() -> Any:
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

    return _session


def make_settings_repo() -> SettingsRepository:
    return SettingsRepository(session_factory=make_session_factory())


def make_message_repo() -> MessageRepository:
    return MessageRepository(session_factory=make_session_factory())


class FakeTray:
    def __init__(self) -> None:
        self.shown: list[tuple[str, str, int]] = []
        self.visible = True

    def showMessage(
        self, title: str, message: str, icon: Any, timeout: int
    ) -> None:  # noqa: N802 (Qt API)
        self.shown.append((title, message, timeout))

    def isVisible(self) -> bool:  # noqa: N802 (Qt API)
        return self.visible


def make_manager(tray: FakeTray | None = None) -> NotificationManager:
    return NotificationManager(
        settings_repo=make_settings_repo(),
        message_repo=make_message_repo(),
        tray=tray,
        sounds_dir="/nonexistent/sounds",
        current_user_id="me",
    )


def test_notify_disabled_by_config() -> None:
    manager = make_manager(tray=FakeTray())
    manager.set_enabled("message", False)
    assert manager.notify("Título", "Msg", type="message") is False
    assert manager.is_enabled("message") is False
    manager.set_enabled("message", True)
    assert manager.is_enabled("message") is True
    assert manager.notify("Título", "Msg", type="message") is True


def test_notify_shows_tray_message_and_callback() -> None:
    tray = FakeTray()
    manager = make_manager(tray=tray)
    callback_called: list[Any] = []

    def on_notify(title: str, message: str) -> None:
        callback_called.append((title, message))

    assert manager.notify("Amigo", "oi", type="message", callback=on_notify) is True
    assert len(tray.shown) == 1
    assert tray.shown[0][0] == "Amigo"
    assert tray.shown[0][1] == "oi"
    assert callback_called == [("Amigo", "oi")]


def test_grouping_same_friend() -> None:
    tray = FakeTray()
    manager = make_manager(tray=tray)
    manager.notify("Amigo", "primeira", type="message", friend_id="friend-1")
    manager.notify("Amigo", "segunda", type="message", friend_id="friend-1")
    assert len(tray.shown) == 2
    grouped = tray.shown[1][1]
    assert "2" in grouped and "Amigo" in grouped


def test_different_friends_not_grouped() -> None:
    tray = FakeTray()
    manager = make_manager(tray=tray)
    manager.notify("A", "oi", type="message", friend_id="a")
    manager.notify("B", "oi", type="message", friend_id="b")
    assert len(tray.shown) == 2
    assert tray.shown[1][1] == "oi"


def test_get_unread_total() -> None:
    repo = make_message_repo()
    manager = NotificationManager(
        settings_repo=make_settings_repo(),
        message_repo=repo,
        tray=None,
        sounds_dir="/nonexistent/sounds",
        current_user_id="me",
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    repo.save_message(
        Message(msg_id="1", sender_id="f1", receiver_id="me", content="a", timestamp=now)
    )
    repo.save_message(
        Message(
            msg_id="2",
            sender_id="f2",
            receiver_id="me",
            content="b",
            timestamp=now,
            read=True,
        )
    )
    repo.save_message(
        Message(
            msg_id="3",
            sender_id="f1",
            receiver_id="me",
            content="c",
            timestamp=now,
        )
    )
    assert repo.get_total_unread("me") == 2
    assert manager.get_unread_total() == 2


def test_volume_and_sound_setting() -> None:
    manager = make_manager()
    manager.set_volume(35)
    assert manager.get_volume() == 35


def test_notify_no_sound_file_no_crash() -> None:
    manager = make_manager(tray=FakeTray())
    assert manager.notify("X", "sem som", type="system") is True


def test_tray_icon_menu_and_tooltip() -> None:
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    from client.app import TrayIcon

    QApplication.instance() or QApplication([])
    tray = TrayIcon()
    tray.set_unread(3)
    assert "3" in tray.toolTip()
    tray.set_unread(0)
    assert "não lida" not in tray.toolTip()

    tray.set_status("dnd")
    assert tray._status_actions["dnd"].isChecked()
    assert not tray._status_actions["online"].isChecked()

    statuses: list[str] = []
    tray.status_requested.connect(statuses.append)
    tray._status_actions["idle"].trigger()
    assert statuses == ["idle"]

    shown: list[bool] = []
    tray.show_requested.connect(lambda: shown.append(True))
    tray._menu.actions()[0].trigger()
    assert shown == [True]

    tray.hide()
