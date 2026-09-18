from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel


class Avatar(QLabel):
    SIZES = {
        "small": 32,
        "medium": 48,
        "large": 64,
    }

    def __init__(
        self,
        size: str = "medium",
        image_path: str = None,
        initials: str = None,
        parent=None,
    ):
        super().__init__(parent)
        self._size_value = self.SIZES.get(size, 48)
        self._image_path = image_path
        self._initials = initials
        self._pixmap = None

        self.setFixedSize(self._size_value, self._size_value)
        self.setAlignment(Qt.AlignCenter)
        self._render()

    def _render(self):
        size = self._size_value
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        if self._image_path and self._pixmap:
            scaled = self._pixmap.scaled(
                size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(0, 0, size, size, QColor("#3d6a8a"))

            if self._initials:
                font = QFont()
                font.setFamily("Segoe UI, Noto Sans, Sans-Serif")
                font.setPixelSize(int(size * 0.4))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QColor("#ffffff"))
                painter.drawText(
                    QRect(0, 0, size, size),
                    Qt.AlignCenter,
                    self._initials[:2].upper(),
                )

        painter.end()
        self.setPixmap(pixmap)

    def set_image(self, image_path: str):
        self._image_path = image_path
        if image_path:
            self._pixmap = QPixmap(image_path)
        self._render()

    def set_initials(self, initials: str):
        self._initials = initials
        self._pixmap = None
        self._render()

    def set_color(self, color: str):
        self._image_path = None
        self._pixmap = None
        self._color = QColor(color)
        self._render()

    def sizeHint(self) -> QSize:
        return QSize(self._size_value, self._size_value)
