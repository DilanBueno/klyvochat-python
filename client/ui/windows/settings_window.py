from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from client.storage.repositories import SettingsRepository
from client.ui.theme import theme
from client.ui.window_manager import FloatingWindow

SETTING_DISPLAY_NAME = "display_name"
SETTING_AUTO_ACCEPT = "auto_accept_requests"
SETTING_NOTIFY_FRIENDS = "notify_new_friends"
SETTING_CHAT_FONT = "chat_font_size"
SETTING_SEND_ENTER = "send_enter"
SETTING_VOICE_INPUT = "voice_input_device"
SETTING_VOICE_OUTPUT = "voice_output_device"
SETTING_VOICE_VOLUME = "voice_volume"
SETTING_THEME = "theme"
SETTING_ACCENT = "accent_color"
SETTING_OPACITY = "window_opacity"


def _int_setting(repo: SettingsRepository, key: str, default: int) -> int:
    try:
        return int(repo.get(key, str(default)) or default)
    except ValueError:
        return default


def _bool_setting(repo: SettingsRepository, key: str, default: bool = True) -> bool:
    raw = repo.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mudar senha")
        self.setModal(True)
        self.setFixedWidth(320)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.current_input = QLineEdit()
        self.current_input.setEchoMode(QLineEdit.Password)
        self.current_input.setPlaceholderText("Senha atual")
        layout.addWidget(self.current_input)

        self.new_input = QLineEdit()
        self.new_input.setEchoMode(QLineEdit.Password)
        self.new_input.setPlaceholderText("Nova senha (mínimo 6 caracteres)")
        layout.addWidget(self.new_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setPlaceholderText("Confirmar nova senha")
        layout.addWidget(self.confirm_input)

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("Salvar")
        save.setDefault(True)
        save.clicked.connect(self._validate)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _validate(self):
        new_password = self.new_input.text()
        if len(new_password) < 6:
            QMessageBox.warning(
                self, "Senha inválida", "A nova senha deve ter ao menos 6 caracteres."
            )
            return
        if new_password != self.confirm_input.text():
            QMessageBox.warning(self, "Senha inválida", "As senhas não conferem.")
            return
        self.accept()


class SettingsWindow(FloatingWindow):
    """Settings window shown as a standalone floating widget."""

    logout_requested = Signal()
    display_name_saved = Signal(str)
    theme_changed = Signal(str)
    accent_changed = Signal(str)
    opacity_changed = Signal(int)
    auto_accept_changed = Signal(bool)
    notify_friends_changed = Signal(bool)
    chat_font_changed = Signal(int)
    send_enter_changed = Signal(bool)
    backup_requested = Signal()
    test_mic_requested = Signal(bool)

    def __init__(
        self,
        *,
        settings_repo: SettingsRepository | None = None,
        current_user: Any | None = None,
        audio_stream: Any | None = None,
        parent=None,
    ) -> None:
        self._settings = settings_repo if settings_repo is not None else SettingsRepository()
        self._user = current_user
        self._audio_stream = audio_stream
        self._mic_test_active = False
        super().__init__(width=500, height=450, parent=parent)
        self._load_settings()

    def _init_ui(self):
        self.title_label.setText("Configurações")
        layout = self.get_content_layout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_account_tab(), "Conta")
        self.tabs.addTab(self._build_friends_tab(), "Amigos")
        self.tabs.addTab(self._build_chat_tab(), "Chat")
        self.tabs.addTab(self._build_voice_tab(), "Voz")
        self.tabs.addTab(self._build_appearance_tab(), "Aparência")
        layout.addWidget(self.tabs)

    # --- tabs --------------------------------------------------------------

    def _build_account_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Nome de exibição")
        form.addRow("Nome de exibição", self.display_name_input)

        save_name_btn = QPushButton("Salvar nome")
        save_name_btn.clicked.connect(self._on_save_display_name)
        form.addRow("", save_name_btn)

        email = getattr(self._user, "email", "") or ""
        email_label = QLabel(email or "—")
        email_label.setStyleSheet("color: #8b98a5;")
        form.addRow("Email", email_label)

        change_password_btn = QPushButton("Mudar senha")
        change_password_btn.clicked.connect(self._on_change_password)
        form.addRow("Senha", change_password_btn)

        form.addRow("", QLabel(""))

        self.logout_btn = QPushButton("Sair da conta")
        self.logout_btn.setObjectName("danger")
        self.logout_btn.clicked.connect(self.logout_requested.emit)
        form.addRow("", self.logout_btn)
        return tab

    def _build_friends_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        self.auto_accept_check = QCheckBox("Aceitar automaticamente pedidos de amizade")
        self.auto_accept_check.toggled.connect(self._on_auto_accept_toggled)
        form.addRow("", self.auto_accept_check)

        self.notify_friends_check = QCheckBox("Notificar quando alguém me adicionar")
        self.notify_friends_check.toggled.connect(self._on_notify_friends_toggled)
        form.addRow("", self.notify_friends_check)
        return tab

    def _build_chat_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 20)
        self.font_spin.setValue(13)
        self.font_spin.valueChanged.connect(self._on_chat_font_changed)
        form.addRow("Tamanho da fonte", self.font_spin)

        self.send_enter_check = QCheckBox("Enviar com Enter (desative para usar Ctrl+Enter)")
        self.send_enter_check.toggled.connect(self._on_send_enter_toggled)
        form.addRow("", self.send_enter_check)

        backup_btn = QPushButton("Fazer backup das conversas")
        backup_btn.clicked.connect(self.backup_requested.emit)
        form.addRow("", backup_btn)
        return tab

    def _build_voice_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        self.input_combo = QComboBox()
        self.output_combo = QComboBox()
        devices = self._audio_stream.list_devices() if self._audio_stream is not None else []
        for device in devices:
            if device.get("inputs", 0) > 0:
                self.input_combo.addItem(device["name"], device["id"])
            if device.get("outputs", 0) > 0:
                self.output_combo.addItem(device["name"], device["id"])
        if self.input_combo.count() == 0:
            self.input_combo.addItem("Padrão", None)
        if self.output_combo.count() == 0:
            self.output_combo.addItem("Padrão", None)
        form.addRow("Dispositivo de entrada", self.input_combo)
        form.addRow("Dispositivo de saída", self.output_combo)

        test_row = QHBoxLayout()
        self.test_mic_btn = QPushButton("Testar microfone")
        self.test_mic_btn.clicked.connect(self._on_test_mic)
        test_row.addWidget(self.test_mic_btn)
        self.mic_level = QProgressBar()
        self.mic_level.setRange(0, 100)
        self.mic_level.setValue(0)
        self.mic_level.setTextVisible(False)
        test_row.addWidget(self.mic_level, 1)
        form.addRow("", test_row)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        form.addRow("Volume", self.volume_slider)
        return tab

    def _build_appearance_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(10)

        theme_row = QHBoxLayout()
        self.dark_radio = QRadioButton("Escuro")
        self.light_radio = QRadioButton("Claro")
        self.dark_radio.toggled.connect(self._on_theme_toggled)
        self.light_radio.toggled.connect(self._on_theme_toggled)
        theme_row.addWidget(self.dark_radio)
        theme_row.addWidget(self.light_radio)
        theme_row.addStretch()
        form.addRow("Tema", theme_row)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(6)
        self._accent_buttons: list[QPushButton] = []
        for color in theme.ACCENTS:
            button = QPushButton()
            button.setFixedSize(22, 22)
            button.setStyleSheet(
                f"QPushButton {{ background-color: {color}; border: 2px solid #3a4a5a;"
                f" border-radius: 11px; }}"
            )
            button.clicked.connect(lambda checked=False, c=color: self._on_accent(c))
            accent_row.addWidget(button)
            self._accent_buttons.append(button)
        accent_row.addStretch()
        form.addRow("Cor de destaque", accent_row)

        opacity_row = QHBoxLayout()
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(70, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider)
        self.opacity_value = QLabel("100%")
        opacity_row.addWidget(self.opacity_value)
        form.addRow("Opacidade da janela", opacity_row)

        note = QLabel(
            "Nota: o tema claro aplica-se às janelas de configurações e diálogos; "
            "as janelas flutuantes mantêm o visual escuro nesta versão."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8b98a5; font-size: 11px;")
        form.addRow("", note)
        return tab

    # --- handlers ----------------------------------------------------------

    def _on_save_display_name(self):
        name = self.display_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Nome inválido", "Informe um nome de exibição.")
            return
        self._settings.set(SETTING_DISPLAY_NAME, name)
        self.display_name_saved.emit(name)

    def _on_auto_accept_toggled(self, enabled: bool):
        self._settings.set(SETTING_AUTO_ACCEPT, "1" if enabled else "0")
        self.auto_accept_changed.emit(enabled)

    def _on_notify_friends_toggled(self, enabled: bool):
        self._settings.set(SETTING_NOTIFY_FRIENDS, "1" if enabled else "0")
        self.notify_friends_changed.emit(enabled)

    def _on_send_enter_toggled(self, enabled: bool):
        self._settings.set(SETTING_SEND_ENTER, "1" if enabled else "0")
        self.send_enter_changed.emit(enabled)

    def _on_change_password(self):
        dialog = ChangePasswordDialog(self)
        dialog.exec()
        if dialog.result() == QDialog.Accepted:
            QMessageBox.information(
                self,
                "Mudar senha",
                "A troca de senha ainda não está disponível no servidor.",
            )

    def _on_chat_font_changed(self, value: int):
        self._settings.set(SETTING_CHAT_FONT, str(value))
        self.chat_font_changed.emit(value)

    def _on_volume_changed(self, value: int):
        self._settings.set(SETTING_VOICE_VOLUME, str(value))

    def _on_test_mic(self):
        self._mic_test_active = not self._mic_test_active
        self.test_mic_btn.setText("Parar teste" if self._mic_test_active else "Testar microfone")
        self.test_mic_requested.emit(self._mic_test_active)

    def set_mic_level(self, level: float):
        self.mic_level.setValue(int(max(0.0, min(1.0, level)) * 100))

    def _on_theme_toggled(self, checked: bool):
        if not checked:
            return
        name = "light" if self.light_radio.isChecked() else "dark"
        self._settings.set(SETTING_THEME, name)
        self.theme_changed.emit(name)

    def _on_accent(self, color: str):
        self._settings.set(SETTING_ACCENT, color)
        self.accent_changed.emit(color)

    def _on_opacity_changed(self, value: int):
        self.opacity_value.setText(f"{value}%")
        self._settings.set(SETTING_OPACITY, str(value))
        self.opacity_changed.emit(value)

    def _load_settings(self):
        for widget in (
            self.auto_accept_check,
            self.notify_friends_check,
            self.send_enter_check,
            self.dark_radio,
            self.light_radio,
        ):
            widget.blockSignals(True)

        self.display_name_input.setText(self._settings.get(SETTING_DISPLAY_NAME, "") or "")
        self.auto_accept_check.setChecked(_bool_setting(self._settings, SETTING_AUTO_ACCEPT, False))
        self.notify_friends_check.setChecked(
            _bool_setting(self._settings, SETTING_NOTIFY_FRIENDS, True)
        )
        self.font_spin.setValue(_int_setting(self._settings, SETTING_CHAT_FONT, 13))
        self.send_enter_check.setChecked(_bool_setting(self._settings, SETTING_SEND_ENTER, True))
        self.volume_slider.setValue(_int_setting(self._settings, SETTING_VOICE_VOLUME, 70))
        self.opacity_slider.setValue(_int_setting(self._settings, SETTING_OPACITY, 100))
        self.opacity_value.setText(f"{self.opacity_slider.value()}%")

        theme_name = self._settings.get(SETTING_THEME, "dark") or "dark"
        self.dark_radio.setChecked(theme_name != "light")
        self.light_radio.setChecked(theme_name == "light")

        input_device = self._settings.get(SETTING_VOICE_INPUT)
        output_device = self._settings.get(SETTING_VOICE_OUTPUT)
        self._select_combo_data(self.input_combo, input_device)
        self._select_combo_data(self.output_combo, output_device)

        for widget in (
            self.auto_accept_check,
            self.notify_friends_check,
            self.send_enter_check,
            self.dark_radio,
            self.light_radio,
        ):
            widget.blockSignals(False)

    @staticmethod
    def _select_combo_data(combo: QComboBox, value: Any):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


__all__ = [
    "ChangePasswordDialog",
    "SETTING_ACCENT",
    "SETTING_AUTO_ACCEPT",
    "SETTING_CHAT_FONT",
    "SETTING_DISPLAY_NAME",
    "SETTING_NOTIFY_FRIENDS",
    "SETTING_OPACITY",
    "SETTING_SEND_ENTER",
    "SETTING_THEME",
    "SETTING_VOICE_INPUT",
    "SETTING_VOICE_OUTPUT",
    "SETTING_VOICE_VOLUME",
    "SettingsWindow",
]
