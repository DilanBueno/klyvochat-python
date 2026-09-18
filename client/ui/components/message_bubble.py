from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class MessageBubble(QFrame):
    def __init__(
        self,
        text: str,
        timestamp: str,
        is_sent: bool = True,
        parent=None,
        font_size: int = 13,
    ):
        super().__init__(parent)
        self._text = text
        self._timestamp = timestamp
        self._is_sent = is_sent
        self._font_size = font_size
        self._setup_ui()

    def _setup_ui(self):
        bg_color = "#1a6e3e" if self._is_sent else "#2a475e"
        align = Qt.AlignRight if self._is_sent else Qt.AlignLeft

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 12px;
                border-bottom-{'right' if self._is_sent else 'left'}-radius: 4px;
                padding: 8px 12px;
                max-width: 280px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.text_label = QLabel(self._text)
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(f"""
            QLabel {{
                color: #ffffff;
                font-size: {self._font_size}px;
                background: transparent;
            }}
        """)
        layout.addWidget(self.text_label, 0, align)

        self.timestamp_label = QLabel(self._timestamp)
        self.timestamp_label.setStyleSheet("""
            QLabel {
                color: #8b98a5;
                font-size: 10px;
                background: transparent;
            }
        """)
        layout.addWidget(self.timestamp_label, 0, align)

    def set_text(self, text: str):
        self._text = text
        self.text_label.setText(text)

    def set_timestamp(self, timestamp: str):
        self._timestamp = timestamp
        self.timestamp_label.setText(timestamp)


class TypingIndicator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._dots = ["", "", ""]
        self._current_dot = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(300)

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #2a475e;
                border-radius: 12px;
                border-bottom-left-radius: 4px;
                padding: 12px 16px;
                max-width: 60px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.dots_label = QLabel("...")
        self.dots_label.setStyleSheet("""
            QLabel {
                color: #8b98a5;
                font-size: 16px;
                background: transparent;
            }
        """)
        layout.addWidget(self.dots_label)

    def _animate(self):
        self._current_dot = (self._current_dot + 1) % 4
        self.dots_label.setText("." * self._current_dot)

    def stop(self):
        self._timer.stop()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
