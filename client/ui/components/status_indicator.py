from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QWidget


class StatusIndicator(QWidget):
    STATUS_COLORS = {
        "online": "#4caf50",
        "idle": "#ffc107",
        "dnd": "#f44336",
        "offline": "#607d8b",
    }

    def __init__(self, status: str = "offline", size: int = 10, parent=None):
        super().__init__(parent)
        self._status = status
        self._size = size
        self.setFixedSize(size + 2, size + 2)

    def set_status(self, status: str):
        if status in self.STATUS_COLORS:
            self._status = status
            self.update()

    def get_status(self) -> str:
        return self._status

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(self.STATUS_COLORS.get(self._status, "#607d8b"))

        border_color = QColor("#1b2838")
        painter.setPen(QPen(border_color, 1))

        painter.setBrush(QBrush(color))
        painter.drawEllipse(1, 1, self._size, self._size)

    def sizeHint(self) -> QSize:
        return QSize(self._size + 2, self._size + 2)
