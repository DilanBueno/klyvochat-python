from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from client.core.messaging import MessageData
from client.ui.components import Avatar, MessageBubble, StatusIndicator, TypingIndicator
from client.ui.window_manager import FloatingWindow

FONT_STYLES = {
    "name": """
        QLabel {
            color: #c7d5e0;
            font-size: 13px;
            font-weight: bold;
            background: transparent;
        }
    """,
    "status": """
        QLabel {
            color: #8b98a5;
            font-size: 11px;
            background: transparent;
        }
    """,
    "typing": """
        QLabel {
            color: #66c0f4;
            font-size: 11px;
            background: transparent;
            padding-left: 16px;
        }
    """,
    "connecting": """
        QLabel {
            color: #ffc107;
            font-size: 11px;
            background: transparent;
        }
    """,
    "error": """
        QLabel {
            color: #f44336;
            font-size: 11px;
            background: transparent;
        }
    """,
    "badge": """
        QPushButton {
            background-color: #f44336;
            color: #ffffff;
            border: none;
            border-radius: 10px;
            padding: 2px 10px;
            font-size: 11px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #d32f2f;
        }
    """,
}


class ChatInput(QTextEdit):
    submit = Signal()
    text_changed = Signal()

    def __init__(self, parent=None, send_enter: bool = True, font_size: int = 13):
        super().__init__(parent)
        self._send_enter = send_enter
        self.setAcceptRichText(False)
        self.setFixedHeight(48)
        self.setMaximumHeight(120)
        self.setPlaceholderText("Escreva uma mensagem...")
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #2a475e;
                color: #c7d5e0;
                border: none;
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #66c0f4;
            }
            """)
        self.textChanged.connect(self.text_changed.emit)

    def set_send_enter(self, enabled: bool) -> None:
        self._send_enter = bool(enabled)

    def keyPressEvent(self, event):  # noqa: N802 (Qt override)
        enter = event.key() in (Qt.Key_Return, Qt.Key_Enter)
        if enter:
            if self._send_enter and not (event.modifiers() & Qt.ShiftModifier):
                self.submit.emit()
                event.accept()
                return
            if not self._send_enter and (event.modifiers() & Qt.ControlModifier):
                self.submit.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class ChatWindow(FloatingWindow):
    send_requested = Signal(str, str)
    typing = Signal(str)
    call_requested = Signal(str)
    window_closed = Signal(str)

    def __init__(
        self,
        friend_id: str,
        name: str,
        status: str = "offline",
        parent=None,
        font_size: int = 13,
        send_enter: bool = True,
    ):
        self.friend_id = str(friend_id)
        self._friend_name = name
        self._status = status
        self._font_size = font_size
        self._send_enter = send_enter
        self._is_typing = False
        self._unread_new = 0
        super().__init__(width=400, height=550, parent=parent)

    def _init_ui(self):
        self.title_label.setText(self._friend_name)
        content = self.get_content_layout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)

        content.addWidget(self._build_header())
        content.addWidget(self._build_status_bar())
        content.addWidget(self._build_messages_area(), 1)
        content.addWidget(self._build_input_area())

    def _build_header(self):
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background-color: #162230; border-bottom: 1px solid #3a4a5a; }"
        )
        header.setFixedHeight(64)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.avatar = Avatar(size="medium", initials=self._initials(self._friend_name))
        layout.addWidget(self.avatar)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.name_label = QLabel(self._friend_name)
        self.name_label.setStyleSheet(FONT_STYLES["name"])
        info.addWidget(self.name_label)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status_indicator = StatusIndicator(status=self._status, size=8)
        status_row.addWidget(self.status_indicator)
        self.status_text = QLabel(self._status.capitalize())
        self.status_text.setStyleSheet(FONT_STYLES["status"])
        status_row.addWidget(self.status_text)
        status_row.addStretch()

        self.call_btn = QPushButton("📞")
        self.call_btn.setFixedSize(28, 28)
        self.call_btn.setCursor(Qt.PointingHandCursor)
        self.call_btn.setToolTip("Chamada de voz")
        self.call_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a475e;
                color: #c7d5e0;
                border: none;
                border-radius: 14px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3a5870;
            }
            """)
        self.call_btn.clicked.connect(lambda: self.call_requested.emit(self.friend_id))
        status_row.addWidget(self.call_btn)

        info.addLayout(status_row)

        layout.addLayout(info, 1)
        return header

    def _build_status_bar(self):
        self.status_bar = QWidget()
        self.status_bar.setStyleSheet("background-color: #1b2838;")
        layout = QVBoxLayout(self.status_bar)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        self.connecting_label = QLabel("Conectando...")
        self.connecting_label.setStyleSheet(FONT_STYLES["connecting"])
        self.connecting_label.hide()
        layout.addWidget(self.connecting_label)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(FONT_STYLES["error"])
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.typing_indicator = TypingIndicator()
        self.typing_indicator.hide()
        layout.addWidget(self.typing_indicator)
        return self.status_bar

    def _build_messages_area(self):
        self.messages_area = QScrollArea()
        self.messages_area.setWidgetResizable(True)
        self.messages_area.setStyleSheet("""
            QScrollArea {
                background-color: #1b2838;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #1b2838;
            }
            """)

        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(10, 10, 10, 10)
        self.messages_layout.setSpacing(6)
        self.messages_layout.addStretch()

        self.messages_area.setWidget(self.messages_container)
        self.messages_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        return self.messages_area

    def _build_input_area(self):
        bottom = QFrame()
        bottom.setStyleSheet("QFrame { background-color: #1b2838; border-top: 1px solid #3a4a5a; }")
        layout = QVBoxLayout(bottom)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        self.new_messages_btn = QPushButton("novas mensagens")
        self.new_messages_btn.setCursor(Qt.PointingHandCursor)
        self.new_messages_btn.setStyleSheet(FONT_STYLES["badge"])
        self.new_messages_btn.setVisible(False)
        self.new_messages_btn.clicked.connect(self._jump_to_bottom)
        layout.addWidget(self.new_messages_btn, 0, Qt.AlignHCenter)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.input_edit = ChatInput(send_enter=self._send_enter, font_size=self._font_size)
        self.input_edit.submit.connect(self._on_submit)
        self.input_edit.text_changed.connect(self._on_text_changed)
        input_row.addWidget(self.input_edit, 1)

        self.send_btn = QPushButton("Enviar")
        self.send_btn.setFixedSize(72, 48)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #66c0f4;
                color: #1b2838;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8cd0f8;
            }
            QPushButton:disabled {
                background-color: #2a475e;
                color: #5a6570;
            }
            """)
        self.send_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.send_btn)

        layout.addLayout(input_row)
        return bottom

    # --- public API --------------------------------------------------------

    def set_status(self, status: str):
        self._status = status
        self.status_indicator.set_status(status)
        self.status_text.setText(status.capitalize())
        self.hide_connecting()

    def set_connecting(self, connecting: bool = True):
        if connecting:
            self.connecting_label.setText("Conectando...")
            self.connecting_label.show()
            self.error_label.hide()
        else:
            self.connecting_label.hide()

    def show_connection_error(self, message: str = "Não foi possível conectar."):
        self.connecting_label.hide()
        self.error_label.setText(message)
        self.error_label.show()

    def hide_connection_error(self):
        self.error_label.hide()

    def show_typing(self):
        self.typing_indicator.show()
        self.typing_indicator.start()

    def hide_typing(self):
        self.typing_indicator.hide()
        self.typing_indicator.stop()

    def add_message(self, message: MessageData):
        is_sent = message.sender_id != self.friend_id
        bubble = MessageBubble(
            text=message.content,
            timestamp=self._format_timestamp(message.timestamp),
            is_sent=is_sent,
            font_size=self._font_size,
        )
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, bubble)
        self._on_new_message()

    def set_history(self, messages: list[MessageData]):
        self._clear_messages()
        for message in messages:
            is_sent = message.sender_id != self.friend_id
            self.messages_layout.insertWidget(
                self.messages_layout.count() - 1,
                MessageBubble(
                    text=message.content,
                    timestamp=self._format_timestamp(message.timestamp),
                    is_sent=is_sent,
                    font_size=self._font_size,
                ),
            )
        self._jump_to_bottom()

    def clear_input(self):
        self.input_edit.clear()

    def get_input_text(self) -> str:
        return self.input_edit.toPlainText().strip()

    # --- internals ---------------------------------------------------------

    def _on_submit(self):
        text = self.get_input_text()
        if not text:
            return
        self.send_requested.emit(self.friend_id, text)

    def _on_text_changed(self):
        self.typing.emit(self.friend_id)

    def _on_new_message(self):
        if self._is_scroll_at_bottom():
            self._jump_to_bottom()
        else:
            self._unread_new += 1
            self._update_new_badge()

    def _on_scroll_changed(self, value: int):
        if value >= self.messages_area.verticalScrollBar().maximum() - 20:
            self._jump_to_bottom()

    def _is_scroll_at_bottom(self) -> bool:
        scrollbar = self.messages_area.verticalScrollBar()
        return scrollbar.maximum() - scrollbar.value() <= 20

    def _jump_to_bottom(self):
        scrollbar = self.messages_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self._unread_new = 0
        self._update_new_badge()

    def _update_new_badge(self):
        if self._unread_new > 0:
            self.new_messages_btn.setText(f"{self._unread_new} novas mensagens ↓")
            self.new_messages_btn.setVisible(True)
        else:
            self.new_messages_btn.setVisible(False)

    def _clear_messages(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _format_timestamp(dt: datetime) -> str:
        now = datetime.now()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dt = dt.astimezone().replace(tzinfo=None)
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        if dt.date() == (now - timedelta(days=1)).date():
            return f"Ontem {dt.strftime('%H:%M')}"
        return dt.strftime("%d/%m %H:%M")

    @staticmethod
    def _initials(name: str) -> str:
        parts = [part for part in str(name).replace("@", " ").split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2]
        return f"{parts[0][0]}{parts[1][0]}"

    def closeEvent(self, event):  # noqa: N802 (Qt override)
        self.typing_indicator.stop()
        super().closeEvent(event)
        if event.isAccepted():
            self.window_closed.emit(self.friend_id)


__all__ = ["ChatInput", "ChatWindow"]
