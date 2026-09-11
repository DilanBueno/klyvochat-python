import sys
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PySide6.QtGui import QPainter, QPainterPath, QColor, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsDropShadowEffect,
    QApplication,
)


class FloatingWindow(QWidget):
    CORNER_RADIUS = 12
    SHADOW_OFFSET = 0
    SHADOW_BLUR = 20
    SHADOW_COLOR = QColor(0, 0, 0, 100)

    def __init__(self, width: int = 400, height: int = 500, parent=None):
        super().__init__(parent)
        self._drag_position = QPoint()
        self._is_closing = False

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(width, height)
        self.resize(width, height)

        self._setup_shadow()
        self._init_base_ui()
        self._setup_animations()
        self._init_ui()

    def _setup_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(self.SHADOW_BLUR)
        shadow.setColor(self.SHADOW_COLOR)
        shadow.setOffset(self.SHADOW_OFFSET, self.SHADOW_OFFSET)
        self.setGraphicsEffect(shadow)

    def _init_base_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.title_bar = self._create_title_bar()
        main_layout.addWidget(self.title_bar)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("content")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(8)
        main_layout.addWidget(self.content_widget)

    def _init_ui(self):
        pass

    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet(
            """
            #titleBar {
                background-color: #162230;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """
        )

        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(8)

        self.title_label = QLabel("Klyvochat")
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
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.minimize_btn = QPushButton()
        self.minimize_btn.setFixedSize(28, 28)
        self.minimize_btn.setObjectName("minimizeBtn")
        self.minimize_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                image: none;
            }
            QPushButton:hover {
                background-color: #2a475e;
            }
        """
        )
        self.minimize_btn.clicked.connect(self.showMinimized)
        layout.addWidget(self.minimize_btn)

        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """
        )
        self.close_btn.clicked.connect(self._animate_close)
        layout.addWidget(self.close_btn)

        self._make_draggable(title_bar)

        return title_bar

    def _make_draggable(self, widget):
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton:
                self._drag_position = event.globalPosition().toPoint()
                event.accept()

        def mouseMoveEvent(event):
            if event.buttons() == Qt.LeftButton:
                delta = event.globalPosition().toPoint() - self._drag_position
                self.move(self.pos() + delta)
                self._drag_position = event.globalPosition().toPoint()
                event.accept()

        widget.mousePressEvent = mousePressEvent
        widget.mouseMoveEvent = mouseMoveEvent

    def _setup_animations(self):
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.pos_animation = QPropertyAnimation(self, b"pos")
        self.pos_animation.setDuration(200)
        self.pos_animation.setEasingCurve(QEasingCurve.InOutQuad)

    def showEvent(self, event):
        super().showEvent(event)
        self._animate_show()

    def _animate_show(self):
        self.opacity_animation.stop()
        self.setWindowOpacity(0)
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(1)
        self.opacity_animation.start()

    def _animate_close(self):
        self._is_closing = True
        self.opacity_animation.stop()
        self.opacity_animation.setStartValue(1)
        self.opacity_animation.setEndValue(0)
        self.opacity_animation.finished.connect(self.close)
        self.opacity_animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            self.rect().adjusted(1, 1, -1, -1),
            self.CORNER_RADIUS,
            self.CORNER_RADIUS,
        )

        painter.fillPath(path, QColor("#1b2838"))

        pen = QPen(QColor("#3a4a5a"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setPen(Qt.NoPen)

    def closeEvent(self, event):
        if self._is_closing:
            event.accept()
        else:
            self._animate_close()
            event.ignore()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def get_content_layout(self) -> QVBoxLayout:
        return self.content_layout
