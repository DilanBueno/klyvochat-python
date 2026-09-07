from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Klyvochat")
        self.resize(400, 500)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Klyvochat - Login"))
        self.setLayout(layout)
