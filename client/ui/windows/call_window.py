from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from client.core.voice import (
    CALL_ACTIVE,
    CALL_CONNECTING,
    CALL_ENDED,
    CALL_IDLE,
    CALL_RINGING_IN,
    CALL_RINGING_OUT,
)
from client.ui.components import Avatar
from client.ui.window_manager import FloatingWindow

STATUS_TEXT = {
    CALL_IDLE: "",
    CALL_RINGING_OUT: "Chamando...",
    CALL_RINGING_IN: "Chamada recebida...",
    CALL_CONNECTING: "Conectando...",
    CALL_ENDED: "Encerrada",
}


class CallWindow(FloatingWindow):
    mute_toggled = Signal(bool)
    end_requested = Signal()

    def __init__(self, friend_id: str, name: str, parent=None):
        self.friend_id = str(friend_id)
        self._friend_name = name
        self._state = CALL_IDLE
        self._muted = False
        self._elapsed = 0
        self._allow_close = False
        super().__init__(width=350, height=120, parent=parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

    def _init_ui(self):
        self.title_label.setText(self._friend_name)
        content = self.get_content_layout()
        content.setContentsMargins(12, 10, 12, 10)
        content.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(12)

        self.avatar = Avatar(size="medium", initials=self._initials(self._friend_name))
        row.addWidget(self.avatar)

        info = QVBoxLayout()
        info.setSpacing(4)
        self.name_label = QLabel(self._friend_name)
        self.name_label.setStyleSheet(
            "QLabel { color: #c7d5e0; font-size: 14px; font-weight: bold; background: transparent; }"
        )
        info.addWidget(self.name_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "QLabel { color: #8b98a5; font-size: 12px; background: transparent; }"
        )
        info.addWidget(self.status_label)

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setFixedHeight(6)
        self.level_bar.setStyleSheet("""
            QProgressBar {
                background-color: #2a475e;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #66c0f4;
                border-radius: 3px;
            }
            """)
        info.addWidget(self.level_bar)

        row.addLayout(info, 1)

        self.mute_btn = QPushButton("🔇")
        self.mute_btn.setFixedSize(40, 40)
        self.mute_btn.setCursor(Qt.PointingHandCursor)
        self.mute_btn.setToolTip("Mutar / desmutar")
        self.mute_btn.setStyleSheet(self._button_style("#2a475e", "#c7d5e0"))
        self.mute_btn.clicked.connect(self._on_mute)
        row.addWidget(self.mute_btn)

        self.end_btn = QPushButton("📞")
        self.end_btn.setFixedSize(40, 40)
        self.end_btn.setCursor(Qt.PointingHandCursor)
        self.end_btn.setToolTip("Encerrar chamada")
        self.end_btn.setStyleSheet(self._button_style("#f44336", "#ffffff"))
        self.end_btn.clicked.connect(self._on_end)
        row.addWidget(self.end_btn)

        content.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def set_state(self, state: str):
        self._state = state
        if state == CALL_ACTIVE:
            self.status_label.setText("00:00")
            self._elapsed = 0
            if not self._timer.isActive():
                self._timer.start()
        elif state in STATUS_TEXT:
            self._timer.stop()
            self.status_label.setText(STATUS_TEXT[state])
        if state in (CALL_ENDED, CALL_IDLE):
            self.set_audio_level(0)

    def set_audio_level(self, level: float):
        value = int(max(0.0, min(1.0, level)) * 100)
        self.level_bar.setValue(value)

    def set_muted(self, muted: bool):
        self._muted = bool(muted)
        self.mute_btn.setText("🔇" if muted else "🎤")
        if muted:
            self.mute_btn.setStyleSheet(self._button_style("#f44336", "#ffffff"))
        else:
            self.mute_btn.setStyleSheet(self._button_style("#2a475e", "#c7d5e0"))

    def force_close(self):
        self._allow_close = True
        self.close()

    def _tick(self):
        if self._state != CALL_ACTIVE:
            return
        self._elapsed += 1
        minutes, seconds = divmod(self._elapsed, 60)
        self.status_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_mute(self):
        self.mute_toggled.emit(not self._muted)

    def _on_end(self):
        self.end_requested.emit()

    @staticmethod
    def _button_style(bg: str, fg: str) -> str:
        return (
            f"QPushButton {{ background-color: {bg}; color: {fg}; border: none;"
            f" border-radius: 20px; font-size: 16px; }}"
            f"QPushButton:hover {{ background-color: {bg}; }}"
        )

    @staticmethod
    def _initials(name: str) -> str:
        parts = [part for part in str(name).replace("@", " ").split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2]
        return f"{parts[0][0]}{parts[1][0]}"

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        if self._allow_close:
            super().closeEvent(event)
        else:
            self.hide()
            event.ignore()


__all__ = ["CallWindow"]
