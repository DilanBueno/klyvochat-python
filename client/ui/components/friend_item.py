from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen

from .avatar import Avatar
from .status_indicator import StatusIndicator


class FriendItem(QFrame):
    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(
        self,
        friend_id: int,
        name: str,
        status: str = "offline",
        description: str = "",
        avatar_initials: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self._friend_id = friend_id
        self._name = name
        self._status = status
        self._description = description
        self._is_hovered = False

        self.setFixedHeight(60)
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui(avatar_initials)
        self._setup_events()

    def _setup_ui(self, avatar_initials):
        self.setStyleSheet(
            """
            QFrame {
                background-color: transparent;
                border-radius: 4px;
            }
            QFrame:hover {
                background-color: #2a475e;
            }
        """
        )

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(12)

        self.avatar = Avatar(size="small", initials=avatar_initials)
        main_layout.addWidget(self.avatar)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setContentsMargins(0, 0, 0, 0)

        name_layout = QHBoxLayout()
        name_layout.setSpacing(4)

        self.name_label = QLabel(self._name)
        self.name_label.setStyleSheet(
            """
            QLabel {
                color: #c7d5e0;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """
        )
        name_layout.addWidget(self.name_label)

        self.status_indicator = StatusIndicator(status=self._status, size=8)
        name_layout.addWidget(self.status_indicator)
        name_layout.addStretch()

        info_layout.addLayout(name_layout)

        self.status_label = QLabel(self._description or self._status.capitalize())
        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #8b98a5;
                font-size: 11px;
                background: transparent;
            }
        """
        )
        info_layout.addWidget(self.status_label)

        main_layout.addLayout(info_layout, 1)

    def _setup_events(self):
        self.mousePressEvent = self._on_click
        self.mouseDoubleClickEvent = self._on_double_click

    def _on_click(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._friend_id)
        super().mousePressEvent(event)

    def _on_double_click(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self._friend_id)
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def set_status(self, status: str):
        self._status = status
        self.status_indicator.set_status(status)
        self.status_label.setText(self._description or self._status.capitalize())

    def set_name(self, name: str):
        self._name = name
        self.name_label.setText(name)

    def set_description(self, description: str):
        self._description = description
        self.status_label.setText(description or self._status.capitalize())

    def get_friend_id(self) -> int:
        return self._friend_id
