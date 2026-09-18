from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .avatar import Avatar


class IncomingCallWidget(QFrame):
    """Pop-up notification for an incoming voice call."""

    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        caller_name: str,
        auto_reject_ms: int = 30_000,
        parent=None,
    ):
        super().__init__(parent)
        self._caller_name = caller_name
        self._auto_reject_ms = auto_reject_ms

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(280, 110)
        self._setup_ui()
        self._setup_animation()
        if auto_reject_ms > 0:
            QTimer.singleShot(auto_reject_ms, self._auto_reject)

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #2a475e;
                border-radius: 8px;
                border: 1px solid #3a4a5a;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.avatar = Avatar(size="medium", initials=self._initials(self._caller_name))
        layout.addWidget(self.avatar)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.name_label = QLabel(self._caller_name)
        self.name_label.setStyleSheet(
            "QLabel { color: #c7d5e0; font-size: 13px; font-weight: bold; background: transparent; }"
        )
        text_layout.addWidget(self.name_label)
        self.call_label = QLabel("Chamada de voz")
        self.call_label.setStyleSheet(
            "QLabel { color: #8b98a5; font-size: 12px; background: transparent; }"
        )
        text_layout.addWidget(self.call_label)
        layout.addLayout(text_layout, 1)

        buttons = QVBoxLayout()
        buttons.setSpacing(6)

        self.accept_btn = QPushButton("Aceitar")
        self.accept_btn.setCursor(Qt.PointingHandCursor)
        self.accept_btn.setStyleSheet(
            "QPushButton { background-color: #4caf50; color: #ffffff; border: none;"
            " border-radius: 12px; padding: 4px 10px; font-size: 12px; }"
            "QPushButton:hover { background-color: #5cbf60; }"
        )
        self.accept_btn.clicked.connect(self.accepted.emit)
        buttons.addWidget(self.accept_btn)

        self.reject_btn = QPushButton("Rejeitar")
        self.reject_btn.setCursor(Qt.PointingHandCursor)
        self.reject_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: #ffffff; border: none;"
            " border-radius: 12px; padding: 4px 10px; font-size: 12px; }"
            "QPushButton:hover { background-color: #d32f2f; }"
        )
        self.reject_btn.clicked.connect(self.rejected.emit)
        buttons.addWidget(self.reject_btn)

        layout.addLayout(buttons)

    def _setup_animation(self):
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(200)
        self.slide_animation.setEasingCurve(QEasingCurve.InOutQuad)

    def showEvent(self, event):  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._animate_show()

    def _animate_show(self):
        self.opacity_animation.stop()
        self.setWindowOpacity(0)
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(1)
        self.opacity_animation.start()

    def _auto_reject(self):
        if self.isVisible():
            self.rejected.emit()

    def close_widget(self):
        self.close()

    def paintEvent(self, event):  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)
        painter.fillPath(path, QColor("#2a475e"))
        pen = QPen(QColor("#3a4a5a"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

    @staticmethod
    def _initials(name: str) -> str:
        parts = [part for part in str(name).replace("@", " ").split() if part]
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0][:2]
        return f"{parts[0][0]}{parts[1][0]}"


class NotificationWidget(QFrame):
    def __init__(
        self,
        title: str,
        message: str,
        duration: int = 5000,
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._message = message
        self._duration = duration
        self._start_pos = QPoint()
        self._end_pos = QPoint()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(320, 100)
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #2a475e;
                border-radius: 8px;
                border: 1px solid #3a4a5a;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #c7d5e0;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b98a5;
                border: none;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #f44336;
                background-color: transparent;
            }
        """)
        self.close_btn.clicked.connect(self._animate_hide)
        header_layout.addWidget(self.close_btn)

        layout.addLayout(header_layout)

        self.message_label = QLabel(self._message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("""
            QLabel {
                color: #8b98a5;
                font-size: 12px;
                background: transparent;
            }
        """)
        layout.addWidget(self.message_label)

    def _setup_animation(self):
        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(200)
        self.slide_animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.opacity_animation.finished.connect(self.close)

        if self._duration > 0:
            QTimer.singleShot(self._duration, self._animate_hide)

    def showEvent(self, event):
        super().showEvent(event)
        self._animate_show()

    def _animate_show(self):
        self.slide_animation.stop()
        self.opacity_animation.stop()

        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(1)
        self.opacity_animation.start()

    def _animate_hide(self):
        self.slide_animation.stop()
        self.opacity_animation.stop()

        self.opacity_animation.setStartValue(1)
        self.opacity_animation.setEndValue(0)
        self.opacity_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        painter.fillPath(path, QColor("#2a475e"))

        pen = QPen(QColor("#3a4a5a"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)


class NotificationManager:
    def __init__(self):
        self._notifications = []

    def show(self, title: str, message: str, duration: int = 5000):
        from PySide6.QtWidgets import QApplication

        notification = NotificationWidget(title, message, duration)

        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            offset_y = 60
            for n in self._notifications:
                if n.isVisible():
                    offset_y += n.height() + 10

            x = screen_geometry.width() - notification.width() - 20
            y = screen_geometry.height() - offset_y - notification.height()
            notification.move(x, y)

        self._notifications.append(notification)
        notification.opacity_animation.finished.connect(
            lambda: self._remove_notification(notification)
        )
        notification.show()

    def _remove_notification(self, notification):
        if notification in self._notifications:
            self._notifications.remove(notification)
