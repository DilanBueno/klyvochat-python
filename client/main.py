from __future__ import annotations

import asyncio
import re
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
)

from client.app import TrayIcon
from client.core.auth import AuthError, AuthManager
from client.core.friends import FriendManager
from client.core.messaging import MessageManager
from client.core.notification_manager import NotificationManager
from client.core.presence import PresenceManager
from client.core.voice import CallManager
from client.network.p2p_manager import P2PManager
from client.network.signaling_client import SignalingClient
from client.security.encryption import MessageEncryption
from client.security.keys import KeyManager
from client.ui.components import IncomingCallWidget
from client.ui.theme import theme
from client.ui.windows.call_window import CallWindow
from client.ui.windows.chat_window import ChatWindow
from client.ui.windows.login_window import LoginWindow
from client.ui.windows.main_window import MainWindow
from client.ui.windows.settings_window import (
    SettingsWindow,
)
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
        self.main_window: MainWindow | None = None
        self.login_window: LoginWindow | None = None
        self.signaling: SignalingClient | None = None
        self.friends: FriendManager | None = None
        self.presence: PresenceManager | None = None
        self.p2p: P2PManager | None = None
        self.messaging: MessageManager | None = None
        self.calls: CallManager | None = None
        self.keys: KeyManager | None = None
        self.encryption: MessageEncryption | None = None
        self.notifications: NotificationManager | None = None
        self._tray: TrayIcon | None = None
        self._chat_windows: dict[str, ChatWindow] = {}
        self._settings_window: SettingsWindow | None = None
        self._mic_test_timer: QTimer | None = None
        self._call_window: CallWindow | None = None
        self._incoming_call_widget: IncomingCallWidget | None = None
        self._session_task: asyncio.Task | None = None

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

    def _open_main_window(self, password: str | None = None) -> None:
        user = self.auth.get_current_user()
        if user is None or not user.id:
            self.auth.logout()
            self._open_login_window()
            return

        self.signaling = SignalingClient(auth_manager=self.auth)
        self.presence = PresenceManager(
            self.signaling,
            current_user_id=str(user.id),
            start_timer=False,
        )
        self.friends = FriendManager(
            self.signaling,
            auth_manager=self.auth,
            presence_manager=self.presence,
            current_user_id=str(user.id),
        )
        self.p2p = P2PManager(
            self.signaling,
            current_user_id=str(user.id),
        )
        self.keys = KeyManager(current_user_id=str(user.id))
        self.encryption = MessageEncryption()
        if password:
            try:
                self.keys.ensure_keys(password)
                self.keys.unlock(password)
            except Exception:
                self.logger.warning("Could not unlock encryption keys", exc_info=True)
        self.messaging = MessageManager(
            self.p2p,
            current_user_id=str(user.id),
            key_manager=self.keys if self.keys.is_unlocked else None,
            encryption=self.encryption if self.keys.is_unlocked else None,
        )
        self.calls = CallManager(
            self.p2p,
            current_user_id=str(user.id),
        )
        self._wire_messaging()
        self._wire_calls()

        self.main_window = MainWindow()
        self._wire_main_window()
        self.main_window.show()
        self._setup_tray()
        self._apply_appearance()
        QTimer.singleShot(0, self._start_session_soon)

    def _wire_main_window(self):
        if self.main_window is None or self.friends is None:
            return
        self.main_window.friend_selected.connect(self._on_friend_selected)
        self.main_window.add_friend_requested.connect(self._on_add_friend_requested)
        self.main_window.profile_requested.connect(self._on_profile_requested)
        self.main_window.delete_conversation_requested.connect(
            self._on_delete_conversation_requested
        )
        self.main_window.remove_friend_requested.connect(self._on_remove_friend_requested)
        self.main_window.friend_request_accepted.connect(self._on_friend_request_accepted)
        self.main_window.friend_request_rejected.connect(self._on_friend_request_rejected)
        self.main_window.closed.connect(self._on_main_window_closed)
        self.main_window.settings_clicked.connect(self._on_settings_clicked)
        self.friends.on_friend_update(self._on_friend_update)
        QApplication.instance().aboutToQuit.connect(self._on_about_to_quit)

    def _wire_messaging(self):
        if self.messaging is None:
            return
        self.messaging.on("message_received", self._on_message_received)
        self.messaging.on("message_delivered", self._on_message_delivered)
        self.messaging.on("typing", self._on_typing)
        self.messaging.on("message_read", self._on_message_read)
        self.messaging.on("conversation_read", self._on_conversation_read)

    def _wire_calls(self):
        if self.calls is None:
            return
        self.calls.on("call_state_changed", self._on_call_state_changed)
        self.calls.on("call_incoming", self._on_call_incoming)
        self.calls.on("call_ended", self._on_call_ended)
        self.calls.on("audio_level", self._on_audio_level)

    def _setup_tray(self) -> None:
        if self.main_window is None:
            return
        tray_available = False
        try:
            tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        except Exception:
            tray_available = False

        if tray_available:
            try:
                self._tray = TrayIcon()
                self._tray.show()
                self._tray.show_requested.connect(self._show_main_window)
                self._tray.toggle_window.connect(self._toggle_main_window)
                self._tray.status_requested.connect(self._on_tray_status)
                self._tray.quit_requested.connect(self._on_quit_requested)
            except Exception:
                self.logger.warning("Could not create tray icon", exc_info=True)
                self._tray = None

        self.notifications = NotificationManager(
            tray=self._tray,
            current_user_id=str(self.auth.get_current_user().id),
        )
        self.main_window.set_minimize_to_tray(self._tray is not None)

    def _show_main_window(self):
        if self.main_window is not None:
            self.main_window.show()
            self.main_window.raise_()
            self.main_window.activateWindow()

    def _toggle_main_window(self):
        if self.main_window is None:
            return
        if self.main_window.isVisible():
            self.main_window.hide()
        else:
            self._show_main_window()

    def _on_tray_status(self, status: str):
        if self.presence is not None:
            asyncio.ensure_future(self.presence.set_status(status))

    def _on_quit_requested(self):
        self._close_session()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _update_tray_unread(self):
        if self._tray is None:
            return
        count = self.notifications.get_unread_total() if self.notifications else 0
        self._tray.set_unread(count)

    def _notify(self, title: str, message: str, type: str, friend_id: str | None = None):
        if self.notifications is None:
            return
        try:
            self.notifications.notify(title, message, type=type, friend_id=friend_id)
        except Exception:
            self.logger.warning("Failed to notify", exc_info=True)

    # --- settings / appearance ---------------------------------------------

    def _on_settings_clicked(self):
        if self._settings_window is not None and self._settings_window.isVisible():
            self._settings_window.raise_()
            self._settings_window.activateWindow()
            return
        from client.storage.repositories import SettingsRepository

        audio_stream = self.calls.audio_stream if self.calls is not None else None
        window = SettingsWindow(
            settings_repo=SettingsRepository(),
            current_user=self.auth.get_current_user(),
            audio_stream=audio_stream,
        )
        window.logout_requested.connect(self._on_settings_logout)
        window.display_name_saved.connect(self._on_display_name_saved)
        window.theme_changed.connect(self._on_theme_changed)
        window.accent_changed.connect(self._on_accent_changed)
        window.opacity_changed.connect(self._on_opacity_changed)
        window.auto_accept_changed.connect(self._on_auto_accept_changed)
        window.notify_friends_changed.connect(self._on_notify_friends_changed)
        window.chat_font_changed.connect(self._on_chat_font_changed)
        window.send_enter_changed.connect(self._on_send_enter_changed)
        window.backup_requested.connect(self._on_backup_requested)
        window.test_mic_requested.connect(self._on_test_mic_requested)
        self._settings_window = window
        window.show()
        window.raise_()

    def _on_settings_logout(self):
        self.logout()

    def _on_display_name_saved(self, name: str):
        from client.storage.repositories import UserRepository

        user = self.auth.get_current_user()
        if user is not None and user.id:
            UserRepository().update_display_name(user.id, name)
            if self.main_window is not None:
                self.main_window.title_label.setText("Klyvochat")
        self.logger.info("Display name saved: %s", name)

    def _on_theme_changed(self, name: str):
        theme.set_theme(name)
        theme.apply(QApplication.instance())

    def _on_accent_changed(self, color: str):
        theme.set_accent(color)
        theme.apply(QApplication.instance())

    def _on_opacity_changed(self, value: int):
        opacity = value / 100.0
        if self.main_window is not None:
            self.main_window.set_window_opacity(opacity)
        for window in self._chat_windows.values():
            window.set_window_opacity(opacity)

    def _on_auto_accept_changed(self, enabled: bool):
        if self.friends is not None:
            self.friends.set_auto_accept(enabled)

    def _on_notify_friends_changed(self, enabled: bool):
        if self.notifications is not None:
            self.notifications.set_enabled("friend_accept", enabled)

    def _on_chat_font_changed(self, value: int):
        for window in self._chat_windows.values():
            window.input_edit.setFontSize(value)
        self.logger.info("Chat font size: %d", value)

    def _on_send_enter_changed(self, enabled: bool):
        for window in self._chat_windows.values():
            window.input_edit.set_send_enter(enabled)

    def _on_backup_requested(self):
        path, _ = QFileDialog.getSaveFileName(
            self._settings_window,
            "Salvar backup das conversas",
            "klyvochat-backup.json",
            "JSON (*.json)",
        )
        if not path:
            return
        try:
            count = self._export_conversations(path)
            QMessageBox.information(
                self._settings_window,
                "Backup concluído",
                f"{count} conversa(s) exportada(s) para {path}.",
            )
        except Exception as exc:
            QMessageBox.warning(
                self._settings_window,
                "Falha no backup",
                str(exc),
            )

    def _export_conversations(self, path: str) -> int:
        import json as json_module

        from client.storage.repositories import MessageRepository

        user_id = self.auth.get_current_user().id
        repo = MessageRepository()
        export: dict[str, Any] = {"version": 1, "user_id": user_id, "conversations": {}}
        friends = self.friends.get_friend_list() if self.friends is not None else []
        for friend in friends:
            friend_id = str(getattr(friend, "friend_id", friend))
            messages = repo.get_conversation(user_id, friend_id, limit=10_000)
            export["conversations"][friend_id] = [
                {
                    "sender_id": m.sender_id,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "encrypted": m.encrypted,
                }
                for m in messages
            ]
        with open(path, "w", encoding="utf-8") as handle:
            json_module.dump(export, handle, ensure_ascii=False, indent=2)
        return len(export["conversations"])

    def _on_test_mic_requested(self, active: bool):
        if self.calls is None:
            return
        audio = self.calls.audio_stream
        if active:
            try:
                audio.start_capture()
            except Exception as exc:
                self.logger.warning("Mic test could not start: %s", exc)
                if self._settings_window is not None:
                    self._settings_window.test_mic_btn.setText("Testar microfone")
                return
            self._mic_test_timer = QTimer()
            self._mic_test_timer.setInterval(100)
            self._mic_test_timer.timeout.connect(self._poll_mic_level)
            self._mic_test_timer.start()
        else:
            audio.stop_capture()
            if self._mic_test_timer is not None:
                self._mic_test_timer.stop()
                self._mic_test_timer = None
            if self._settings_window is not None:
                self._settings_window.set_mic_level(0)

    def _poll_mic_level(self):
        if self.calls is None or self._settings_window is None:
            return
        self._settings_window.set_mic_level(self.calls.audio_stream.get_energy())

    def _apply_appearance(self):
        from client.storage.repositories import SettingsRepository

        repo = SettingsRepository()
        theme_name = repo.get("theme", "dark") or "dark"
        accent = repo.get("accent_color")
        theme.set_theme(theme_name)
        if accent:
            theme.set_accent(accent)
        theme.apply(QApplication.instance())
        try:
            opacity = int(repo.get("window_opacity", "100") or 100) / 100.0
        except ValueError:
            opacity = 1.0
        if self.main_window is not None:
            self.main_window.set_window_opacity(opacity)
        auto_accept = (repo.get("auto_accept_requests", "0") or "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if self.friends is not None:
            self.friends.set_auto_accept(auto_accept)
        notify_friends = (repo.get("notify_new_friends", "1") or "1").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if self.notifications is not None:
            self.notifications.set_enabled("friend_accept", notify_friends)

    def logout(self):
        self._close_session()
        if self.main_window is not None:
            self.main_window.set_minimize_to_tray(False)
            self.main_window.close()
            self.main_window = None
        self.auth.logout()
        self._open_login_window()

    async def _start_session(self) -> None:
        if self.main_window is None or self.signaling is None:
            return
        self.main_window.set_loading(True)
        try:
            await self.signaling.connect()
            if self.presence is not None:
                await self.presence.set_status("online")
                self.presence.start()
            if self.friends is not None:
                friends = await self.friends.load_friends()
                self.main_window.set_friends(friends)
                self.main_window.set_pending_requests(self.friends.get_pending_requests())
            self.main_window.set_loading(False)
        except Exception as exc:
            self.logger.exception("Failed to initialize friends session")
            self.main_window.set_loading(False)
            self.main_window.set_error(f"Não foi possível conectar: {exc}")

    def _start_session_soon(self) -> None:
        self._session_task = asyncio.ensure_future(self._start_session())

    def _on_friend_selected(self, friend_id: str):
        self.logger.info("Friend selected: %s", friend_id)
        friend_id = str(friend_id)
        window = self._chat_windows.get(friend_id)
        if window is None:
            window = self._create_chat_window(friend_id)
        window.show()
        window.raise_()
        window.activateWindow()
        self._refresh_chat_window(friend_id)

    def _create_chat_window(self, friend_id: str) -> ChatWindow:
        friend = self._get_friend(friend_id)
        name = getattr(friend, "display_name", None) or friend_id
        status = getattr(friend, "status", "offline") or "offline"
        if self.presence is not None:
            status = self.presence.get_friend_status(friend_id) or status
        font_size = 13
        send_enter = True
        try:
            from client.storage.repositories import SettingsRepository

            repo = SettingsRepository()
            font_size = int(repo.get("chat_font_size", "13") or 13)
            send_enter = (repo.get("send_enter", "1") or "1").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        except ValueError:
            pass
        window = ChatWindow(
            friend_id,
            name,
            status=status,
            font_size=font_size,
            send_enter=send_enter,
        )
        window.send_requested.connect(self._on_chat_send)
        window.typing.connect(self._on_chat_typing)
        window.call_requested.connect(self._on_call_requested)
        window.window_closed.connect(self._on_chat_window_closed)
        self._chat_windows[friend_id] = window
        return window

    def _get_friend(self, friend_id: str):
        if self.friends is None:
            return None
        for friend in self.friends.get_friend_list():
            if str(getattr(friend, "friend_id", friend)) == str(friend_id):
                return friend
        return None

    def _refresh_chat_window(self, friend_id: str):
        window = self._chat_windows.get(friend_id)
        if window is None or self.messaging is None:
            return
        window.set_history(self.messaging.get_conversation(friend_id, limit=50))
        if self.main_window is not None:
            self.main_window.clear_friend_unread(friend_id)
        asyncio.ensure_future(self._mark_read_and_connect(friend_id, window))

    async def _mark_read_and_connect(self, friend_id: str, window: ChatWindow):
        if self.messaging is None or self.friends is None:
            return
        try:
            await self.messaging.mark_conversation_read(friend_id)
        except Exception:
            self.logger.warning("Failed to mark conversation as read", exc_info=True)
        friend = self._get_friend(friend_id)
        is_online = bool(friend is not None and getattr(friend, "status", "offline") != "offline")
        if not is_online:
            window.set_status("offline")
            return
        if self.p2p is None:
            return
        window.set_connecting(True)
        try:
            await self.p2p.connect_to_peer(friend_id)
            await self._wait_open(friend_id, window)
        except Exception:
            window.show_connection_error()

    async def _wait_open(self, friend_id: str, window: ChatWindow):
        if self.p2p is None:
            return
        if self.p2p.is_connected(friend_id):
            window.set_connecting(False)
            window.hide_connection_error()
            return
        opened = asyncio.Event()

        def _on_open(peer: str):
            if str(peer) == friend_id:
                opened.set()

        self.p2p.on("data_channel_open", _on_open)
        try:
            try:
                await asyncio.wait_for(opened.wait(), timeout=15)
                window.set_connecting(False)
                window.hide_connection_error()
            except TimeoutError:
                window.set_connecting(False)
                window.show_connection_error()
        finally:
            self.p2p.off("data_channel_open", _on_open)

    def _on_chat_send(self, friend_id: str, content: str):
        asyncio.ensure_future(self._send_chat_message(friend_id, content))

    async def _send_chat_message(self, friend_id: str, content: str):
        window = self._chat_windows.get(friend_id)
        if self.messaging is None:
            if window is not None:
                window.show_connection_error()
            return
        try:
            message = await self.messaging.send_message(friend_id, content)
        except Exception:
            self.logger.warning("Failed to send message", exc_info=True)
            message = None
        if window is None:
            return
        if message is not None:
            window.add_message(message)
            window.clear_input()
            window.hide_connection_error()
        else:
            window.show_connection_error()

    def _on_chat_typing(self, friend_id: str):
        if self.messaging is None:
            return
        asyncio.ensure_future(self.messaging.notify_typing(friend_id))

    def _on_chat_window_closed(self, friend_id: str):
        self._chat_windows.pop(str(friend_id), None)

    def _on_message_received(self, message: Any):
        friend_id = getattr(message, "sender_id", None)
        if friend_id is None:
            return
        friend_id = str(friend_id)
        window = self._chat_windows.get(friend_id)
        if window is not None and window.isVisible():
            window.add_message(message)
            if self.messaging is not None:
                asyncio.ensure_future(self.messaging.mark_conversation_read(friend_id))
            if self.main_window is not None:
                self.main_window.clear_friend_unread(friend_id)
        else:
            if self.messaging is not None and self.main_window is not None:
                self.main_window.set_friend_unread(
                    friend_id, self.messaging.get_unread_count(friend_id)
                )
            friend = self._get_friend(friend_id)
            name = getattr(friend, "display_name", None) or friend_id
            self._notify(
                name,
                getattr(message, "content", "") or "Nova mensagem",
                type="message",
                friend_id=friend_id,
            )
        self._update_tray_unread()

    def _on_message_delivered(self, msg_id: str):
        self.logger.debug("Message delivered: %s", msg_id)

    def _on_typing(self, friend_id: str, is_typing: bool):
        window = self._chat_windows.get(str(friend_id))
        if window is None or not window.isVisible():
            return
        if is_typing:
            window.show_typing()
        else:
            window.hide_typing()

    def _on_message_read(self, friend_id: str):
        self.logger.debug("Friend read messages: %s", friend_id)

    def _on_conversation_read(self, friend_id: str):
        if self.main_window is not None:
            self.main_window.clear_friend_unread(friend_id)
        self._update_tray_unread()

    # --- calls -------------------------------------------------------------

    def _on_call_requested(self, friend_id: str):
        asyncio.ensure_future(self._start_call(friend_id))

    async def _start_call(self, friend_id: str):
        if self.calls is None:
            return
        self._close_incoming_call_widget()
        window = self._call_window
        if window is not None and self.calls.is_in_call:
            window.set_state(self.calls.state)
            window.show()
            return
        friend = self._get_friend(friend_id)
        name = getattr(friend, "display_name", None) or friend_id
        self._call_window = CallWindow(friend_id, name)
        self._call_window.mute_toggled.connect(self._on_call_mute)
        self._call_window.end_requested.connect(self._on_call_end)
        self._call_window.set_state("connecting")
        self._call_window.show()
        try:
            await self.calls.start_call(friend_id)
        except Exception as exc:
            self.logger.warning("Failed to start call: %s", exc)
            self._call_window.set_state("ended")
            self._call_window.set_audio_level(0)
            QTimer.singleShot(1500, self._call_window.force_close)

    def _on_call_mute(self, muted: bool):
        if self.calls is not None:
            actual = self.calls.toggle_mute()
            if self._call_window is not None:
                self._call_window.set_muted(actual)

    def _on_call_end(self):
        if self.calls is not None:
            asyncio.ensure_future(self.calls.end_call())

    def _on_call_incoming(self, call_id: str, friend_id: str, offer: Any):
        friend = self._get_friend(friend_id)
        name = getattr(friend, "display_name", None) or friend_id
        self._notify(
            name,
            "Chamada de voz recebida",
            type="call",
            friend_id=friend_id,
        )
        self._close_incoming_call_widget()
        widget = IncomingCallWidget(name)
        widget.accepted.connect(lambda: self._accept_call(call_id, friend_id, offer))
        widget.rejected.connect(lambda: self._reject_call(call_id, friend_id))
        widget.rejected.connect(self._close_incoming_call_widget)
        self._incoming_call_widget = widget
        widget.show()
        self._position_incoming_call_widget(widget)

    def _position_incoming_call_widget(self, widget: IncomingCallWidget):
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            widget.move(100, 100)
            return
        geometry = screen.geometry()
        widget.move(
            geometry.width() - widget.width() - 20,
            geometry.height() - widget.height() - 120,
        )

    def _accept_call(self, call_id: str, friend_id: str, offer: Any):
        self._close_incoming_call_widget()
        friend = self._get_friend(friend_id)
        name = getattr(friend, "display_name", None) or friend_id
        self._call_window = CallWindow(friend_id, name)
        self._call_window.mute_toggled.connect(self._on_call_mute)
        self._call_window.end_requested.connect(self._on_call_end)
        self._call_window.set_state("connecting")
        self._call_window.show()
        if self.calls is not None:
            asyncio.ensure_future(self.calls.accept_call(call_id, friend_id, offer))

    def _reject_call(self, call_id: str, friend_id: str):
        if self.calls is not None:
            asyncio.ensure_future(self.calls.reject_call(call_id, friend_id))

    def _on_call_state_changed(self, state: str, friend_id: str | None):
        window = self._call_window
        if window is None:
            return
        window.set_state(state)
        if state == "active":
            window.show()
            window.raise_()

    def _on_call_ended(self, friend_id: str | None, reason: str):
        window = self._call_window
        self._close_incoming_call_widget()
        if window is not None:
            window.set_state("ended")
            QTimer.singleShot(1500, window.force_close)

    def _on_audio_level(self, level: float):
        if self._call_window is not None:
            self._call_window.set_audio_level(level)

    def _close_incoming_call_widget(self):
        if self._incoming_call_widget is not None:
            try:
                self._incoming_call_widget.close()
            except RuntimeError:
                pass
            self._incoming_call_widget = None

    def _on_add_friend_requested(self, email: str):
        asyncio.ensure_future(self._send_friend_request(email))

    async def _send_friend_request(self, email: str):
        if self.main_window is None or self.friends is None:
            return
        self.main_window.set_loading(True, "Enviando pedido...")
        try:
            await self.friends.send_request(email)
            QMessageBox.information(
                self.main_window,
                "Pedido enviado",
                "Pedido de amizade enviado.",
            )
        except Exception as exc:
            QMessageBox.warning(
                self.main_window,
                "Não foi possível adicionar",
                str(exc),
            )
        finally:
            self.main_window.set_loading(False)
            self.main_window.clear_error()

    def _on_profile_requested(self, friend_id: str):
        if self.main_window is None or self.friends is None:
            return
        friend = next(
            (item for item in self.friends.get_friend_list() if item.friend_id == str(friend_id)),
            None,
        )
        if friend is None:
            return
        popup = self.main_window.ProfilePopup(
            friend.to_dict(), is_friend=True, parent=self.main_window
        )
        popup.chat_requested.connect(self._on_friend_selected)
        popup.remove_requested.connect(self._on_remove_friend_requested)
        popup.show()

    def _on_delete_conversation_requested(self, friend_id: str):
        if self.friends is None:
            return
        result = QMessageBox.question(
            self.main_window,
            "Apagar conversa",
            "Apagar todas as mensagens desta conversa?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            return
        try:
            self.friends.delete_conversation(friend_id)
        except Exception as exc:
            QMessageBox.warning(
                self.main_window,
                "Não foi possível apagar",
                str(exc),
            )

    def _on_remove_friend_requested(self, friend_id: str):
        if self.main_window is None or self.friends is None:
            return
        self.main_window.set_loading(True, "Removendo amigo...")

        async def remove():
            try:
                await self.friends.remove_friend(friend_id)
            except Exception as exc:
                QMessageBox.warning(
                    self.main_window,
                    "Não foi possível remover",
                    str(exc),
                )
            finally:
                self.main_window.set_loading(False)
                self.main_window.clear_error()

        asyncio.ensure_future(remove())

    def _on_friend_request_accepted(self, request_id: str):
        if self.main_window is None or self.friends is None:
            return
        self.main_window.set_loading(True, "Aceitando pedido...")

        async def accept():
            try:
                await self.friends.accept_request(request_id)
                self.main_window.set_pending_requests(self.friends.get_pending_requests())
            except Exception as exc:
                QMessageBox.warning(
                    self.main_window,
                    "Não foi possível aceitar",
                    str(exc),
                )
            finally:
                self.main_window.set_loading(False)
                self.main_window.clear_error()

        asyncio.ensure_future(accept())

    def _on_friend_request_rejected(self, request_id: str):
        if self.main_window is None or self.friends is None:
            return
        self.main_window.set_loading(True, "Recusando pedido...")

        async def reject():
            try:
                await self.friends.reject_request(request_id)
                self.main_window.set_pending_requests(self.friends.get_pending_requests())
            except Exception as exc:
                QMessageBox.warning(
                    self.main_window,
                    "Não foi possível recusar",
                    str(exc),
                )
            finally:
                self.main_window.set_loading(False)
                self.main_window.clear_error()

        asyncio.ensure_future(reject())

    def _on_friend_update(self, update: object, event: str):
        if self.main_window is None or self.friends is None:
            return
        if event == "friend_request":
            requester = ""
            if isinstance(update, dict):
                requester = (
                    update.get("requester_name")
                    or update.get("username")
                    or update.get("requester_id")
                    or ""
                )
                self.main_window.show_friend_request(update)
            else:
                self.main_window.show_friend_request(getattr(update, "to_dict", lambda: update)())
                requester = getattr(update, "requester_name", "") or ""
            self.main_window.set_pending_requests(self.friends.get_pending_requests())
            self._notify(
                "Novo pedido de amizade", f"{requester} quer ser seu amigo", type="friend_request"
            )
            return
        if event == "friend_accept":
            if isinstance(update, dict):
                friend_id = update.get("friend_id") or update.get("id")
                name = update.get("name") or update.get("username") or friend_id
            else:
                friend_id = getattr(update, "friend_id", None) or getattr(update, "id", None)
                name = (
                    getattr(update, "display_name", None)
                    or getattr(update, "name", "")
                    or friend_id
                )
            self._notify(
                "Amigo adicionado", f"{name} aceitou seu pedido de amizade", type="friend_accept"
            )
        if event == "friend_remove":
            friend_id = getattr(update, "friend_id", update)
            self.main_window.remove_friend(str(friend_id))
            self._close_chat_window(str(friend_id))
            return
        if event == "auth_ok":
            self.main_window.set_friends(update)
            self.main_window.set_pending_requests(self.friends.get_pending_requests())
            return
        if isinstance(update, dict):
            self.main_window.upsert_friend(update)
        elif hasattr(update, "friend_id"):
            self.main_window.upsert_friend(update)
        if event == "presence_update":
            self._on_presence_update(update)

    def _on_presence_update(self, update: Any):
        friend_id = getattr(update, "friend_id", None)
        if friend_id is None and isinstance(update, dict):
            friend_id = update.get("friend_id") or update.get("user_id")
        window = self._chat_windows.get(str(friend_id)) if friend_id else None
        if window is None:
            return
        status = getattr(update, "status", None)
        if status is None and isinstance(update, dict):
            status = update.get("status")
        if status:
            window.set_status(str(status))

    def _close_chat_window(self, friend_id: str):
        window = self._chat_windows.pop(str(friend_id), None)
        if window is not None:
            window.close()

    def _on_main_window_closed(self):
        self._close_session()

    def _on_about_to_quit(self):
        self._close_session()

    def _close_session(self):
        if self._session_task is not None and not self._session_task.done():
            self._session_task.cancel()
        for friend_id in list(self._chat_windows):
            self._close_chat_window(friend_id)
        if self._mic_test_timer is not None:
            self._mic_test_timer.stop()
            self._mic_test_timer = None
        if self._settings_window is not None:
            try:
                self._settings_window.close()
            except RuntimeError:
                pass
            self._settings_window = None
        if self.presence is not None:
            self.presence.close()
        if self.friends is not None:
            self.friends.close()
        if self.messaging is not None:
            self.messaging.close()
        if self.calls is not None:
            self.calls.close()
        if self.notifications is not None:
            self.notifications = None
        if self._tray is not None:
            try:
                self._tray.hide()
            except Exception:
                pass
            self._tray = None
        if self.p2p is not None:
            self.p2p.close()
        if self.signaling is not None and self.signaling.is_connected:
            asyncio.ensure_future(self.signaling.disconnect())
        if self.keys is not None:
            self.keys.lock()
        self.presence = None
        self.friends = None
        self.messaging = None
        self.calls = None
        self.keys = None
        self.encryption = None
        self.notifications = None
        self.p2p = None
        self.signaling = None

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
                self._open_main_window(password=data["password"])
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
                self._open_main_window(password=password)
            except AuthError as e:
                self.login_window.show_error(str(e))
            except Exception as e:
                self.logger.error("Login failed", exc_info=e)
                self.login_window.show_error("Erro inesperado. Tente novamente.")
            finally:
                self.login_window.set_loading(False)

        asyncio.ensure_future(do_login())
