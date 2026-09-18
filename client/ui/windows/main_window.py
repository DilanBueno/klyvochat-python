from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..components import FriendItem, SearchBar
from ..window_manager import FloatingWindow
from .profile_popup import ProfilePopup

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MainWindow(FloatingWindow):
    ProfilePopup = ProfilePopup
    friend_selected = Signal(str)
    friend_request_accepted = Signal(str)
    friend_request_rejected = Signal(str)
    add_friend_requested = Signal(str)
    profile_requested = Signal(str)
    delete_conversation_requested = Signal(str)
    remove_friend_requested = Signal(str)
    settings_clicked = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(width=300, height=600, parent=parent)
        self._friends: list[dict[str, Any]] = []
        self._friend_items: dict[str, FriendItem] = {}
        self._sections: list[FriendSection] = []
        self._online_count = 0
        self._offline_count = 0
        self._pending_requests: dict[str, dict[str, Any]] = {}
        self._prompted_requests: set[str] = set()
        self._cleanup_emitted = False
        self._minimize_to_tray = False
        self.center_on_screen()

    def _init_ui(self):
        self.title_label.setText("Klyvochat")
        content_layout = self.get_content_layout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        search_container = QWidget()
        search_container.setStyleSheet(
            "background-color: #1b2838; border-bottom: 1px solid #3a4a5a;"
        )
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(12, 12, 12, 8)
        search_layout.setSpacing(6)

        self.search_bar = SearchBar(placeholder="Buscar amigos...")
        self.search_bar.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_bar)

        self.pending_label = QLabel("0 pedidos de amizade")
        self.pending_label.setStyleSheet(
            "color: #ffc107; font-size: 11px; background: transparent;"
        )
        self.pending_label.hide()
        search_layout.addWidget(self.pending_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8b98a5; font-size: 11px; background: transparent;")
        self.status_label.hide()
        search_layout.addWidget(self.status_label)

        content_layout.addWidget(search_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1b2838;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #1b2838;
            }
            """)

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.addStretch()

        self.scroll_area.setWidget(self.scroll_content)
        content_layout.addWidget(self.scroll_area, 1)

        self._setup_empty_state()

        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background-color: #1b2838; border-top: 1px solid #3a4a5a;")

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 0, 12, 0)

        self.add_friend_btn = QPushButton("+")
        self.add_friend_btn.setFixedSize(36, 36)
        self.add_friend_btn.setCursor(Qt.PointingHandCursor)
        self.add_friend_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a475e;
                color: #c7d5e0;
                border: none;
                border-radius: 18px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a5870;
            }
            QPushButton:disabled {
                background-color: #203444;
                color: #5a6570;
            }
            """)
        self.add_friend_btn.clicked.connect(self._on_add_friend_clicked)
        footer_layout.addWidget(self.add_friend_btn)

        footer_layout.addStretch()

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b98a5;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2a475e;
                color: #c7d5e0;
            }
            """)
        self.settings_btn.clicked.connect(lambda: self.settings_clicked.emit())
        footer_layout.addWidget(self.settings_btn)

        content_layout.addWidget(footer)

    def _setup_empty_state(self):
        self.empty_widget = QWidget()
        self.empty_widget.hide()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(20, 40, 20, 20)

        empty_icon = QLabel("👥")
        empty_icon.setAlignment(Qt.AlignCenter)
        empty_icon.setStyleSheet("""
            QLabel {
                font-size: 48px;
                background: transparent;
            }
            """)
        empty_layout.addWidget(empty_icon)

        empty_label = QLabel("Nenhum amigo ainda")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("""
            QLabel {
                color: #8b98a5;
                font-size: 14px;
                background: transparent;
                margin-top: 12px;
            }
            """)
        empty_layout.addWidget(empty_label)

        empty_hint = QLabel("Clique em + para adicionar")
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_hint.setStyleSheet("""
            QLabel {
                color: #5a6570;
                font-size: 12px;
                background: transparent;
                margin-top: 4px;
            }
            """)
        empty_layout.addWidget(empty_hint)

        self.scroll_layout.insertWidget(0, self.empty_widget)

    def set_friends(self, friends: list[Any]):
        self._friends = [self._normalize_friend(friend) for friend in friends]
        self._friends = [friend for friend in self._friends if friend is not None]
        self._render_friends()

    def upsert_friend(self, friend: Any):
        normalized = self._normalize_friend(friend)
        if normalized is None:
            return
        friend_id = normalized["friend_id"]
        self._friends = [item for item in self._friends if item["friend_id"] != friend_id]
        self._friends.append(normalized)
        self._render_friends()

    def remove_friend(self, friend_id: str):
        friend_id = str(friend_id)
        self._friends = [friend for friend in self._friends if friend.get("friend_id") != friend_id]
        self._render_friends()

    def set_friend_unread(self, friend_id: str, count: int):
        item = self._friend_items.get(str(friend_id))
        if item is not None:
            item.set_unread(int(count))

    def clear_friend_unread(self, friend_id: str):
        self.set_friend_unread(friend_id, 0)

    def set_pending_requests(self, requests: list[Any]):
        incoming_requests = {}
        for request in requests:
            if isinstance(request, dict):
                data = request
            elif hasattr(request, "to_dict"):
                data = request.to_dict()
            else:
                continue
            direction = str(data.get("direction", "incoming")).lower()
            if direction == "outgoing":
                continue
            request_id = data.get("request_id") or data.get("id")
            if request_id:
                incoming_requests[str(request_id)] = data
        self._pending_requests = incoming_requests
        self._prompted_requests.intersection_update(self._pending_requests)
        self._update_pending_label()

    def show_friend_request(self, request: Any):
        if isinstance(request, dict):
            data = request
        elif hasattr(request, "to_dict"):
            data = request.to_dict()
        else:
            return
        request_id = data.get("request_id") or data.get("id")
        if not request_id:
            return
        request_id = str(request_id)
        if request_id in self._prompted_requests:
            self._update_pending_label()
            return
        self._pending_requests[request_id] = data
        self._prompted_requests.add(request_id)
        self._update_pending_label()
        QTimer.singleShot(0, lambda: self._ask_friend_request(data, request_id))

    def _ask_friend_request(self, request: dict[str, Any], request_id: str):
        name = request.get("requester_name") or request.get("username") or request_id
        result = QMessageBox.question(
            self,
            "Pedido de amizade",
            f"{name} enviou um pedido de amizade.\n\nAceitar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if result == QMessageBox.Yes:
            self.friend_request_accepted.emit(request_id)
        else:
            self.friend_request_rejected.emit(request_id)

    def set_loading(self, loading: bool, message: str = "Conectando..."):
        if loading:
            self.status_label.setText(message)
            self.status_label.show()
            self.add_friend_btn.setEnabled(False)
        else:
            self.status_label.hide()
            self.add_friend_btn.setEnabled(True)

    def set_error(self, message: str):
        if not message:
            self.status_label.hide()
            return
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #f44336; font-size: 11px; background: transparent;")
        self.status_label.show()

    def clear_error(self):
        self.status_label.setStyleSheet("color: #8b98a5; font-size: 11px; background: transparent;")
        self.status_label.hide()

    def _on_search_changed(self, text: str):
        for section in self._sections:
            section.filter_items(text)

    def _on_add_friend_clicked(self):
        email, accepted = QInputDialog.getText(
            self,
            "Adicionar amigo",
            "Email do amigo:",
        )
        if not accepted:
            return
        email = email.strip()
        if not EMAIL_RE.match(email):
            QMessageBox.warning(self, "Email inválido", "Informe um email válido.")
            return
        self.add_friend_requested.emit(email)

    def _show_context_menu(self, pos, friend_item: FriendItem):
        friend_id = friend_item.get_friend_id()
        menu = QMenu(self)

        profile_action = menu.addAction("Ver perfil")
        delete_chat_action = menu.addAction("Apagar conversa")
        menu.addSeparator()
        remove_action = menu.addAction("Remover amigo")

        action = menu.exec_(friend_item.mapToGlobal(pos))

        if action == profile_action:
            self.profile_requested.emit(friend_id)
        elif action == delete_chat_action:
            self.delete_conversation_requested.emit(friend_id)
        elif action == remove_action:
            result = QMessageBox.question(
                self,
                "Remover amigo",
                "Remover este amigo da sua lista?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result == QMessageBox.Yes:
                self.remove_friend_requested.emit(friend_id)

    def _render_friends(self):
        search_text = self.search_bar.text()
        self._clear_friend_sections()
        self._online_count = sum(1 for friend in self._friends if self._is_online(friend))
        self._offline_count = len(self._friends) - self._online_count

        online_section = None
        offline_section = None
        for friend in sorted(
            self._friends,
            key=lambda item: str(item.get("name") or item.get("username") or "").lower(),
        ):
            is_online = self._is_online(friend)
            if is_online:
                if online_section is None:
                    online_section = self._add_section(
                        f"Online — {self._online_count}", insert=True
                    )
                self._add_friend_to_section(online_section, friend)
            else:
                if offline_section is None:
                    offline_section = self._add_section(
                        f"Offline — {self._offline_count}", insert=False
                    )
                self._add_friend_to_section(offline_section, friend)

        self._update_empty_state()
        if search_text:
            self._on_search_changed(search_text)

    def _add_section(self, title: str, insert: bool) -> FriendSection:
        section = FriendSection(title)
        section.friend_selected.connect(self.friend_selected.emit)
        if insert:
            self.scroll_layout.insertWidget(1, section)
        else:
            self.scroll_layout.addWidget(section)
        section.show()
        self._sections.append(section)
        return section

    def _add_friend_to_section(self, section: FriendSection, friend: dict[str, Any]):
        section.add_friend(friend)
        friend_item = section.items_by_id.get(friend["friend_id"])
        if friend_item is not None:
            friend_item.customContextMenuRequested.connect(
                lambda pos, item=friend_item: self._show_context_menu(pos, item)
            )
            self._friend_items[friend["friend_id"]] = friend_item

    def _clear_friend_sections(self):
        for section in list(self._sections):
            section.deleteLater()
        self._sections.clear()
        self._friend_items.clear()
        index = 0
        while index < self.scroll_layout.count():
            item = self.scroll_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, FriendSection):
                self.scroll_layout.takeAt(index)
            else:
                index += 1

    def _update_empty_state(self):
        has_friends = bool(self._friends)
        self.empty_widget.setVisible(not has_friends)
        self.scroll_area.setVisible(True)

    def _update_pending_label(self):
        count = len(self._pending_requests)
        if count:
            self.pending_label.setText(f"{count} pedido(s) de amizade")
            self.pending_label.show()
        else:
            self.pending_label.hide()

    def _normalize_friend(self, friend: Any) -> dict[str, Any] | None:
        if isinstance(friend, dict):
            data = friend
        elif hasattr(friend, "to_dict"):
            data = friend.to_dict()
        else:
            return None
        friend_id = data.get("friend_id") or data.get("id") or data.get("user_id")
        if not friend_id:
            return None
        name = data.get("name") or data.get("nickname") or data.get("username") or friend_id
        return {
            "id": data.get("id") or friend_id,
            "friend_id": str(friend_id),
            "user_id": data.get("user_id") or friend_id,
            "username": data.get("username") or "",
            "name": name,
            "email": data.get("email") or "",
            "status": data.get("status") or "offline",
            "nickname": data.get("nickname"),
            "added_at": data.get("added_at"),
        }

    def _is_online(self, friend: dict[str, Any]) -> bool:
        return friend.get("status", "offline") != "offline"

    def _initials(self, name: str) -> str:
        parts = [part for part in str(name).replace("@", " ").split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2]
        return f"{parts[0][0]}{parts[1][0]}"

    def set_minimize_to_tray(self, enabled: bool):
        self._minimize_to_tray = bool(enabled)

    def closeEvent(self, event):
        if self._minimize_to_tray:
            self.hide()
            event.ignore()
            return
        if not self._cleanup_emitted:
            self._cleanup_emitted = True
            self.closed.emit()
        super().closeEvent(event)


class FriendSection(QWidget):
    friend_selected = Signal(str)

    def __init__(self, title: str = "Amigos", parent=None):
        super().__init__(parent)
        self._title = title
        self._base_title = title
        self._items: list[FriendItem] = []
        self.items_by_id: dict[str, FriendItem] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        self.header = QLabel(self._title)
        self.header.setFixedHeight(24)
        self.header.setStyleSheet("""
            QLabel {
                color: #8b98a5;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
            }
            """)
        layout.addWidget(self.header)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(2)
        layout.addWidget(self.items_container)

    def add_friend(self, friend_data: dict[str, Any]):
        friend_id = str(friend_data.get("friend_id") or friend_data.get("id"))
        if friend_id in self.items_by_id:
            self.update_friend(friend_data)
            return
        friend_item = FriendItem(
            friend_id=friend_id,
            name=friend_data.get("name") or friend_data.get("username") or friend_id,
            status=friend_data.get("status", "offline"),
            description=friend_data.get("email") or "",
            avatar_initials=friend_data.get("initials"),
        )
        friend_item.double_clicked.connect(self.friend_selected.emit)
        self.items_layout.addWidget(friend_item)
        self._items.append(friend_item)
        self.items_by_id[friend_id] = friend_item

    def update_friend(self, friend_data: dict[str, Any]):
        friend_id = str(friend_data.get("friend_id") or friend_data.get("id"))
        item = self.items_by_id.get(friend_id)
        if item is None:
            self.add_friend(friend_data)
            return
        item.set_name(friend_data.get("name") or friend_data.get("username") or friend_id)
        item.set_description(friend_data.get("email") or "")
        item.set_status(friend_data.get("status", "offline"))

    def remove_friend(self, friend_id: str):
        friend_id = str(friend_id)
        item = self.items_by_id.pop(friend_id, None)
        if item is not None:
            self._items.remove(item)
            item.deleteLater()

    def update_title(self, title: str):
        self._title = title
        self.header.setText(title)

    def count(self) -> int:
        return len(self._items)

    def filter_items(self, text: str):
        text_lower = text.lower()
        for item in self._items:
            item.setVisible(text_lower in item.name.lower())

        visible_count = sum(1 for item in self._items if item.isVisible())
        if visible_count == 0 and text:
            self.hide()
        else:
            self.show()
            self.update_title(f"{self._base_title.split('—')[0].strip()} — {visible_count}")

    @property
    def name(self) -> str:
        return self._title
