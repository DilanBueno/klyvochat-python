from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton

from ..components import Avatar, StatusIndicator
from ..window_manager import FloatingWindow


def _format_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime("%d/%m/%Y")


class ProfilePopup(FloatingWindow):
    chat_requested = Signal(str)
    remove_requested = Signal(str)
    add_friend_requested = Signal(str)

    def __init__(
        self,
        friend: dict[str, Any],
        *,
        is_friend: bool = True,
        parent=None,
    ) -> None:
        self._friend = friend
        self._is_friend = is_friend
        super().__init__(width=280, height=320, parent=parent)
        self.setWindowFlags(self.windowFlags() | Qt.Popup)

    def _init_ui(self):
        self.title_label.setText("Perfil")
        layout = self.get_content_layout()
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        friend_id = str(self._friend.get("friend_id") or self._friend.get("id") or "")
        name = (
            self._friend.get("name")
            or self._friend.get("display_name")
            or self._friend.get("username")
            or friend_id
        )
        username = self._friend.get("username") or ""
        email = self._friend.get("email") or ""
        status = str(self._friend.get("status", "offline"))

        avatar = Avatar(size="large", initials=self._initials(name))
        avatar.setAlignment(Qt.AlignCenter)
        layout.addWidget(avatar)

        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet(
            "QLabel { font-size: 14pt; font-weight: bold; color: #c7d5e0; background: transparent; }"
        )
        layout.addWidget(name_label)

        if username:
            username_label = QLabel(f"@{username}")
            username_label.setAlignment(Qt.AlignCenter)
            username_label.setStyleSheet(
                "QLabel { color: #8b98a5; font-size: 12px; background: transparent; }"
            )
            layout.addWidget(username_label)

        if email:
            email_label = QLabel(email)
            email_label.setAlignment(Qt.AlignCenter)
            email_label.setStyleSheet(
                "QLabel { color: #5a6570; font-size: 11px; background: transparent; }"
            )
            layout.addWidget(email_label)

        status_row = QHBoxLayout()
        status_row.addStretch()
        status_row.addWidget(StatusIndicator(status=status, size=8))
        status_label = QLabel(status.capitalize())
        status_label.setStyleSheet(
            "QLabel { color: #8b98a5; font-size: 12px; background: transparent; }"
        )
        status_row.addWidget(status_label)
        status_row.addStretch()
        layout.addLayout(status_row)

        member_since = _format_date(self._friend.get("added_at") or self._friend.get("created_at"))
        if member_since:
            member_label = QLabel(f"Membro desde: {member_since}")
            member_label.setAlignment(Qt.AlignCenter)
            member_label.setStyleSheet(
                "QLabel { color: #5a6570; font-size: 11px; background: transparent; }"
            )
            layout.addWidget(member_label)

        layout.addStretch()

        if self._is_friend:
            chat_button = QPushButton("Iniciar Conversa")
            chat_button.clicked.connect(lambda: self.chat_requested.emit(friend_id))
            layout.addWidget(chat_button)

            remove_button = QPushButton("Remover Amigo")
            remove_button.setObjectName("danger")
            remove_button.clicked.connect(lambda: self._confirm_remove(friend_id))
            layout.addWidget(remove_button)
        else:
            add_button = QPushButton("Enviar Pedido de Amizade")
            add_button.clicked.connect(lambda: self.add_friend_requested.emit(friend_id))
            layout.addWidget(add_button)

    def _confirm_remove(self, friend_id: str):
        result = QMessageBox.question(
            self,
            "Remover amigo",
            "Remover este amigo da sua lista?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result == QMessageBox.Yes:
            self.remove_requested.emit(friend_id)

    @staticmethod
    def _initials(name: str) -> str:
        parts = [part for part in str(name).replace("@", " ").split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2]
        return f"{parts[0][0]}{parts[1][0]}"


__all__ = ["ProfilePopup"]
