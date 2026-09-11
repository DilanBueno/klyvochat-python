from __future__ import annotations

import asyncio
import re
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpacerItem, QSizePolicy

from client.core.auth import AuthManager, AuthError
from client.ui.windows.login_window import LoginWindow
from client.ui.windows.main_window import MainWindow
from client.utils.logger import get_logger


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar conta")
        self.setFixedWidth(360)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuário")
        self.username_input.setMinimumHeight(40)
        layout.addWidget(self.username_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email")
        self.email_input.setMinimumHeight(40)
        layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha (mínimo 6 caracteres)")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(40)
        layout.addWidget(self.password_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f44336; font-size: 12px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.create_btn = QPushButton("Criar conta")
        self.create_btn.setMinimumHeight(36)
        self.create_btn.setDefault(True)
        self.create_btn.clicked.connect(self._on_create)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

    def _on_create(self):
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not username or not email or not password:
            self._show_error("Preencha todos os campos")
            return

        if not EMAIL_RE.match(email):
            self._show_error("Email inválido")
            return

        if len(password) < 6:
            self._show_error("Senha deve ter ao menos 6 caracteres")
            return

        self.error_label.hide()
        self.accept()

    def _show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()

    def get_data(self):
        return {
            "username": self.username_input.text().strip(),
            "email": self.email_input.text().strip(),
            "password": self.password_input.text(),
        }


class AppController:
    def __init__(self) -> None:
        self.auth = AuthManager()
        self.logger = get_logger(__name__)

    def start(self) -> None:
        if self.auth.is_authenticated():
            self._open_main_window()
            return

        self._open_login_window()

    def _open_login_window(self) -> None:
        self.login_window = LoginWindow()
        self.login_window.login_requested.connect(self._handle_login)
        self.login_window.register_requested.connect(self._handle_register_request)
        self.login_window.show()

    def _open_main_window(self) -> None:
        self.main_window = MainWindow()
        self.main_window.show()

    def _handle_register_request(self) -> None:
        dialog = RegisterDialog(self.login_window)
        if dialog.exec() != QDialog.Accepted:
            return

        data = dialog.get_data()
        self.login_window.set_loading(True)
        self.login_window.show_error("")

        async def do_register():
            try:
                await self.auth.register(data["username"], data["email"], data["password"])
                self.login_window.close()
                self._open_main_window()
            except AuthError as e:
                self.login_window.show_error(str(e))
            except Exception as e:
                self.logger.error("Register failed", exc_info=e)
                self.login_window.show_error("Erro inesperado. Tente novamente.")
            finally:
                self.login_window.set_loading(False)

        asyncio.ensure_future(do_register())

    def _handle_login(self, username: str, password: str) -> None:
        is_email = "@" in username
        email = username if is_email else ""
        
        if is_email and not EMAIL_RE.match(email):
            self.login_window.show_error("Formato de email inválido")
            return

        if len(password) < 6:
            self.login_window.show_error("Senha deve ter ao menos 6 caracteres")
            return

        self.login_window.set_loading(True)
        self.login_window.show_error("")

        async def do_login():
            try:
                await self.auth.login(email or username, password)
                self.login_window.close()
                self._open_main_window()
            except AuthError as e:
                self.login_window.show_error(str(e))
            except Exception as e:
                self.logger.error("Login failed", exc_info=e)
                self.login_window.show_error("Erro inesperado. Tente novamente.")
            finally:
                self.login_window.set_loading(False)

        asyncio.ensure_future(do_login())
