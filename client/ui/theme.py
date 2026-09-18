from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication


class ThemeManager:
    _instance = None

    COLORS = {
        "bg_primary": "#1b2838",
        "bg_secondary": "#2a475e",
        "bg_tertiary": "#3d6a8a",
        "accent": "#66c0f4",
        "accent_hover": "#89c4eb",
        "accent_pressed": "#4fa8d8",
        "text_primary": "#c7d5e0",
        "text_secondary": "#8b98a5",
        "text_disabled": "#5a6570",
        "success": "#4caf50",
        "error": "#f44336",
        "warning": "#ffc107",
        "border": "#3a4a5a",
        "input_bg": "#2a3f52",
        "input_focus": "#3a5068",
    }

    LIGHT_COLORS = {
        "bg_primary": "#eef1f5",
        "bg_secondary": "#dfe5ec",
        "bg_tertiary": "#c9d3de",
        "accent": "#2f80ed",
        "accent_hover": "#5a9ef2",
        "accent_pressed": "#1f6fd0",
        "text_primary": "#1b2838",
        "text_secondary": "#5a6b7d",
        "text_disabled": "#9aa7b4",
        "success": "#2e9e4f",
        "error": "#d64541",
        "warning": "#e6a817",
        "border": "#c2ccd6",
        "input_bg": "#ffffff",
        "input_focus": "#eef4fb",
    }

    ACCENTS = [
        "#66c0f4",
        "#4caf50",
        "#f44336",
        "#ffc107",
        "#9c27b0",
        "#ff7043",
        "#00bcd4",
    ]

    FONTS = {
        "family": "Segoe UI, Noto Sans, Sans-Serif",
    }

    FONT_SIZES = {
        "small": 10,
        "body": 12,
        "medium": 13,
        "large": 14,
        "title": 16,
        "heading": 18,
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._current_theme = "dark"
            self._accent_override: str | None = None

    @property
    def current_theme(self) -> str:
        return self._current_theme

    def set_theme(self, name: str) -> None:
        if name not in {"dark", "light"}:
            raise ValueError(f"Unknown theme: {name}")
        self._current_theme = name
        self._accent_override = None

    def set_accent(self, color: str) -> None:
        self._accent_override = color

    def _palette(self) -> dict[str, str]:
        return self.LIGHT_COLORS if self._current_theme == "light" else self.COLORS

    def get_color(self, name: str) -> str:
        palette = self._palette()
        if name == "accent" and self._accent_override:
            return self._accent_override
        if name in {"accent_hover", "accent_pressed"} and self._accent_override:
            return self._accent_override
        return palette.get(name, "#000000")

    def apply(self, app=None) -> None:

        target = app or QApplication.instance()
        if target is not None:
            target.setStyleSheet(self.get_stylesheet())

    def get_font(self, size: str = "body") -> QFont:
        font = QFont()
        font.setFamily(self.FONTS["family"])
        font.setPointSize(self.FONT_SIZES.get(size, 12))
        return font

    def get_font_size(self, size: str) -> int:
        return self.FONT_SIZES.get(size, 12)

    def get_qcolor(self, name: str) -> QColor:
        return QColor(self.get_color(name))

    def get_stylesheet(self) -> str:
        return f"""
        QWidget {{
            background-color: {self.get_color("bg_primary")};
            color: {self.get_color("text_primary")};
            font-family: {self.FONTS["family"]};
            font-size: {self.get_font_size("body")}px;
        }}

        QPushButton {{
            background-color: {self.get_color("accent")};
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: {self.get_font_size("body")}px;
            font-weight: bold;
            min-height: 24px;
        }}

        QPushButton:hover {{
            background-color: {self.get_color("accent_hover")};
        }}

        QPushButton:pressed {{
            background-color: {self.get_color("accent_pressed")};
        }}

        QPushButton:disabled {{
            background-color: {self.get_color("text_disabled")};
            color: {self.get_color("bg_secondary")};
        }}

        QPushButton#ghost {{
            background-color: transparent;
            color: {self.get_color("accent")};
            border: 1px solid {self.get_color("accent")};
        }}

        QPushButton#ghost:hover {{
            background-color: {self.get_color("accent")}20;
        }}

        QPushButton#danger {{
            background-color: {self.get_color("error")};
            color: #ffffff;
        }}

        QPushButton#danger:hover {{
            background-color: #e53935;
        }}

        QLineEdit {{
            background-color: {self.get_color("input_bg")};
            color: {self.get_color("text_primary")};
            border: 1px solid {self.get_color("border")};
            border-radius: 4px;
            padding: 10px 12px;
            font-size: {self.get_font_size("body")}px;
            selection-background-color: {self.get_color("accent")};
        }}

        QLineEdit:focus {{
            border-color: {self.get_color("accent")};
            background-color: {self.get_color("input_focus")};
        }}

        QLineEdit:disabled {{
            background-color: {self.get_color("bg_secondary")};
            color: {self.get_color("text_disabled")};
        }}

        QScrollArea {{
            background-color: transparent;
            border: none;
        }}

        QScrollArea > QWidget > QWidget {{
            background-color: transparent;
        }}

        QLabel {{
            background-color: transparent;
            color: {self.get_color("text_primary")};
            font-size: {self.get_font_size("body")}px;
        }}

        QFrame {{
            background-color: transparent;
        }}

        QFrame#card {{
            background-color: {self.get_color("bg_secondary")};
            border-radius: 8px;
            border: 1px solid {self.get_color("border")};
        }}

        QScrollBar:vertical {{
            background-color: transparent;
            width: 8px;
            margin: 0px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {self.get_color("text_disabled")};
            border-radius: 4px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {self.get_color("text_secondary")};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: transparent;
            height: 8px;
            margin: 0px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {self.get_color("text_disabled")};
            border-radius: 4px;
            min-width: 20px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {self.get_color("text_secondary")};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        QMenu {{
            background-color: {self.get_color("bg_secondary")};
            border: 1px solid {self.get_color("border")};
            border-radius: 4px;
            padding: 4px;
        }}

        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 2px;
        }}

        QMenu::item:selected {{
            background-color: {self.get_color("accent")};
        }}

        QMenu::separator {{
            height: 1px;
            background-color: {self.get_color("border")};
            margin: 4px 0px;
        }}
        """

    def apply_theme(self, widget):
        widget.setStyleSheet(self.get_stylesheet())


theme = ThemeManager()
