from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

TRAY_STATUSES = {"online": "Online", "idle": "Idle", "dnd": "Do Not Disturb"}


class TrayIcon(QSystemTrayIcon):
    """System tray icon with menu, presence status and unread counter."""

    show_requested = Signal()
    toggle_window = Signal()
    quit_requested = Signal()
    status_requested = Signal(str)

    def __init__(self, parent: Any | None = None) -> None:
        super().__init__(parent)
        self.setIcon(self._make_icon())
        self.setToolTip("Klyvochat")
        self._menu = QMenu()
        self._status_actions: dict[str, QAction] = {}
        self._setup_menu()
        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    def _setup_menu(self) -> None:
        open_action = QAction("Abrir Klyvochat", self._menu)
        open_action.triggered.connect(self.show_requested.emit)
        self._menu.addAction(open_action)

        self._menu.addSeparator()

        status_group: list[QAction] = []
        for value, label in TRAY_STATUSES.items():
            action = QAction(label, self._menu)
            action.setCheckable(True)
            action.setChecked(value == "online")
            action.triggered.connect(lambda checked, v=value: self.status_requested.emit(v))
            self._menu.addAction(action)
            self._status_actions[value] = action
            status_group.append(action)

        self._menu.addSeparator()

        quit_action = QAction("Sair", self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

    def set_unread(self, count: int) -> None:
        if count > 0:
            self.setToolTip(f"Klyvochat — {count} não lida(s)")
        else:
            self.setToolTip("Klyvochat")

    def set_status(self, status: str) -> None:
        for value, action in self._status_actions.items():
            action.setChecked(value == status)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_window.emit()

    @staticmethod
    def _make_icon(size: int = 64) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRect(2, 2, size - 4, size - 4), 14, 14)
        painter.fillPath(path, QColor("#2a475e"))
        painter.setPen(QColor("#66c0f4"))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(size * 0.5))
        painter.setFont(font)
        painter.setPen(QColor("#66c0f4"))
        painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, "K")
        painter.end()
        return QIcon(pixmap)


__all__ = ["TRAY_STATUSES", "TrayIcon"]
