from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QMenu,
)

from ..window_manager import FloatingWindow
from ..theme import theme
from ..components import SearchBar, FriendItem, Avatar


class MainWindow(FloatingWindow):
    friend_double_clicked = Signal(int)
    settings_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(width=300, height=600, parent=parent)
        self._friends = []
        self._online_count = 0
        self._offline_count = 0
        self.center_on_screen()

    def _init_ui(self):
        self.title_label.setText("Klyvochat")
        content_layout = self.get_content_layout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        search_container = QWidget()
        search_container.setStyleSheet("background-color: #1b2838;")
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(12, 12, 12, 8)
        search_layout.setSpacing(8)

        self.search_bar = SearchBar(placeholder="Buscar amigos...")
        self.search_bar.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_bar)

        content_layout.addWidget(search_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: #1b2838;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #1b2838;
            }
        """
        )

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
        self.add_friend_btn.setStyleSheet(
            """
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
        """
        )
        footer_layout.addWidget(self.add_friend_btn)

        footer_layout.addStretch()

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(36, 36)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.setStyleSheet(
            """
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
        """
        )
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
        empty_icon.setStyleSheet(
            """
            QLabel {
                font-size: 48px;
                background: transparent;
            }
        """
        )
        empty_layout.addWidget(empty_icon)

        empty_label = QLabel("Nenhum amigo ainda")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet(
            """
            QLabel {
                color: #8b98a5;
                font-size: 14px;
                background: transparent;
                margin-top: 12px;
            }
        """
        )
        empty_layout.addWidget(empty_label)

        empty_hint = QLabel("Clique em + para adicionar")
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_hint.setStyleSheet(
            """
            QLabel {
                color: #5a6570;
                font-size: 12px;
                background: transparent;
                margin-top: 4px;
            }
        """
        )
        empty_layout.addWidget(empty_hint)

        self.scroll_layout.insertWidget(0, self.empty_widget)

    def _on_search_changed(self, text: str):
        for i in range(self.scroll_layout.count() - 1):
            widget = self.scroll_layout.itemAt(i).widget()
            if isinstance(widget, FriendSection):
                widget.filter_items(text)

    def _create_section_header(self, title: str) -> QLabel:
        header = QLabel(title)
        header.setFixedHeight(28)
        header.setStyleSheet(
            """
            QLabel {
                color: #8b98a5;
                font-size: 11px;
                font-weight: bold;
                background-color: #1b2838;
                padding: 4px 12px;
            }
        """
        )
        return header

    def set_friends(self, friends: list):
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._friends = friends
        self._online_count = 0
        self._offline_count = 0

        online_section = None
        offline_section = None

        for friend in friends:
            if friend.get("status") == "online":
                if online_section is None:
                    online_section = FriendSection(
                        title=f"Online — {len([f for f in friends if f.get('status') == 'online'])}"
                    )
                    self.scroll_layout.insertWidget(0, online_section)
                online_section.add_friend(friend)
                self._online_count += 1
            else:
                if offline_section is None:
                    offline_section = FriendSection(
                        title=f"Offline — {len([f for f in friends if f.get('status') != 'online'])}"
                    )
                    self.scroll_layout.addWidget(offline_section)
                offline_section.add_friend(friend)
                self._offline_count += 1

        self._update_empty_state()

    def add_friend(self, friend_data: dict):
        self._friends.append(friend_data)
        status = friend_data.get("status", "offline")

        is_online = status == "online"
        friend_section = None

        for i in range(self.scroll_layout.count()):
            widget = self.scroll_layout.itemAt(i).widget()
            if isinstance(widget, FriendSection):
                if is_online and "Online" in widget.title():
                    friend_section = widget
                    break
                elif not is_online and "Offline" in widget.title():
                    friend_section = widget
                    break

        if friend_section is None:
            friend_section = FriendSection(
                title=f"{'Online' if is_online else 'Offline'} — 1"
            )
            if is_online:
                self.scroll_layout.insertWidget(0, friend_section)
            else:
                self.scroll_layout.addWidget(friend_section)

        friend_section.add_friend(friend_data)
        friend_section.update_title(
            f"{'Online' if is_online else 'Offline'} — {friend_section.count()}"
        )
        self._update_empty_state()

    def _update_empty_state(self):
        self.empty_widget.setVisible(len(self._friends) == 0)
        self.scroll_area.setVisible(len(self._friends) > 0)


class FriendSection(QWidget):
    def __init__(self, title: str = "Amigos", parent=None):
        super().__init__(parent)
        self._title = title
        self._items = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        self.header = QLabel(self._title)
        self.header.setFixedHeight(24)
        self.header.setStyleSheet(
            """
            QLabel {
                color: #8b98a5;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
            }
        """
        )
        layout.addWidget(self.header)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(2)
        layout.addWidget(self.items_container)

    def add_friend(self, friend_data: dict):
        friend_item = FriendItem(
            friend_id=friend_data.get("id"),
            name=friend_data.get("name"),
            status=friend_data.get("status", "offline"),
            description=friend_data.get("description", ""),
            avatar_initials=friend_data.get("initials"),
        )

        friend_item.double_clicked.connect(
            lambda fid: self.parent().parent().friend_double_clicked.emit(fid)
        )
        friend_item.setContextMenuPolicy(Qt.CustomContextMenu)
        friend_item.customContextMenuRequested.connect(
            lambda pos, item=friend_item: self._show_context_menu(pos, item)
        )

        self.items_layout.addWidget(friend_item)
        self._items.append(friend_item)

    def update_title(self, title: str):
        self._title = title
        self.header.setText(title)

    def count(self) -> int:
        return len(self._items)

    def filter_items(self, text: str):
        text_lower = text.lower()
        for item in self._items:
            item.setVisible(text_lower in item._name.lower())

        visible_count = sum(1 for item in self._items if item.isVisible())
        if visible_count == 0 and text:
            self.hide()
        else:
            self.show()
            self.update_title(
                f"{self._title.split('—')[0].strip()} — {visible_count}"
            )

    def _show_context_menu(self, pos, friend_item: FriendItem):
        menu = QMenu(self)

        view_profile_action = menu.addAction("Ver perfil")
        delete_chat_action = menu.addAction("Apagar conversa")
        menu.addSeparator()
        remove_action = menu.addAction("Remover amigo")

        action = menu.exec_(friend_item.mapToGlobal(pos))

        if action == remove_action:
            print(f"Remover amigo: {friend_item.get_friend_id()}")
