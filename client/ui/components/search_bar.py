from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QWidget, QLabel


class SearchBar(QLineEdit):
    def __init__(self, placeholder: str = "Buscar...", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setMinimumHeight(36)
        self.setTextMargins(8, 0, 8, 0)
        self.setStyleSheet(
            """
            QLineEdit {
                background-color: #2a3f52;
                color: #c7d5e0;
                border: 1px solid #3a4a5a;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 12px;
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
