from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QSpacerItem,
    QSizePolicy,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ..window_manager import FloatingWindow
from ..theme import theme


class LoginWindow(FloatingWindow):
    login_requested = Signal(str, str)
    register_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(width=400, height=520, parent=parent)
        self.center_on_screen()

    def _init_ui(self):
        content_layout = self.get_content_layout()
        content_layout.setContentsMargins(32, 40, 32, 32)
        content_layout.setSpacing(16)

        spacer_top = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        content_layout.addItem(spacer_top)

        title_label = QLabel("Klyvochat")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            """
            QLabel#title {
                color: #66c0f4;
                font-size: 28px;
                font-weight: bold;
                font-family: "Segoe UI", "Noto Sans", sans-serif;
                background: transparent;
                margin-bottom: 8px;
            }
        """
        )
        content_layout.addWidget(title_label)

        subtitle_label = QLabel("Conecte-se com seus amigos")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet(
            """
            QLabel {
                color: #8b98a5;
                font-size: 13px;
                background: transparent;
                margin-bottom: 32px;
            }
        """
        )
        content_layout.addWidget(subtitle_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Email ou usuário")
        self.username_input.setMinimumHeight(44)
        self.username_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #2a3f52;
                color: #c7d5e0;
                border: 1px solid #3a4a5a;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #66c0f4;
                background-color: #3a5068;
            }
            QLineEdit::placeholder {
                color: #8b98a5;
            }
        """
        )
        content_layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(44)
        self.password_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #2a3f52;
                color: #c7d5e0;
                border: 1px solid #3a4a5a;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #66c0f4;
                background-color: #3a5068;
            }
            QLineEdit::placeholder {
                color: #8b98a5;
            }
        """
        )
        self.password_input.returnPressed.connect(self._on_login_clicked)
        content_layout.addWidget(self.password_input)

        self.error_label = QLabel("")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setStyleSheet(
            """
            QLabel {
                color: #f44336;
                font-size: 12px;
                background: transparent;
                min-height: 20px;
            }
        """
        )
        self.error_label.hide()
        content_layout.addWidget(self.error_label)

        self.login_btn = QPushButton("Conectar")
        self.login_btn.setMinimumHeight(44)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #66c0f4;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #89c4eb;
            }
            QPushButton:pressed {
                background-color: #4fa8d8;
            }
            QPushButton:disabled {
                background-color: #5a6570;
                color: #3a4a5a;
            }
        """
        )
        self.login_btn.clicked.connect(self._on_login_clicked)
        content_layout.addWidget(self.login_btn)

        spacer_middle = QSpacerItem(0, 16, QSizePolicy.Minimum, QSizePolicy.Fixed)
        content_layout.addItem(spacer_middle)

        self.register_btn = QPushButton("Criar conta")
        self.register_btn.setMinimumHeight(44)
        self.register_btn.setCursor(Qt.PointingHandCursor)
        self.register_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #66c0f4;
                border: 1px solid #66c0f4;
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(102, 192, 244, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(102, 192, 244, 0.2);
            }
        """
        )
        self.register_btn.clicked.connect(self._on_register_clicked)
        content_layout.addWidget(self.register_btn)

        spacer_bottom = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        content_layout.addItem(spacer_bottom)

    def _on_login_clicked(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username:
            self._show_error("Por favor, insira seu email ou usuário")
            return

        if not password:
            self._show_error("Por favor, insira sua senha")
            return

        self._hide_error()
        self.login_requested.emit(username, password)

    def _on_register_clicked(self):
        self.register_requested.emit()

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def _hide_error(self):
        self.error_label.hide()

    def set_loading(self, loading: bool):
        self.login_btn.setEnabled(not loading)
        self.register_btn.setEnabled(not loading)
        self.username_input.setEnabled(not loading)
        self.password_input.setEnabled(not loading)

        if loading:
            self.login_btn.setText("Conectando...")
        else:
            self.login_btn.setText("Conectar")

    def show_error(self, message: str):
        self._show_error(message)

    def clear(self):
        self.username_input.clear()
        self.password_input.clear()
        self._hide_error()
