from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget
from PySide6.QtGui import QPainter, QPainterPath, QColor


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
        self.setStyleSheet(
            """
            QFrame {
                background-color: #2a475e;
                border-radius: 8px;
                border: 1px solid #3a4a5a;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(4)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel(self._title)
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #c7d5e0;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }
        """
        )
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet(
            """
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
        """
        )
        self.close_btn.clicked.connect(self._animate_hide)
        header_layout.addWidget(self.close_btn)

        layout.addLayout(header_layout)

        self.message_label = QLabel(self._message)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            """
            QLabel {
                color: #8b98a5;
                font-size: 12px;
                background: transparent;
            }
        """
        )
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
