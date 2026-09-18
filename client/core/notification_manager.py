from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from client.storage.repositories import MessageRepository, SettingsRepository

logger = logging.getLogger(__name__)

NOTIFICATION_TYPES = frozenset({"message", "call", "friend_request", "friend_accept", "system"})

SOUND_FILES: dict[str, str] = {
    "message": "message.ogg",
    "call": "call.ogg",
    "friend_request": "notify.ogg",
    "friend_accept": "notify.ogg",
    "system": "notify.ogg",
}

ENABLED_SETTING: dict[str, str] = {
    "message": "notif_message_enabled",
    "call": "notif_call_enabled",
    "friend_request": "notif_friend_request_enabled",
    "friend_accept": "notif_friend_accept_enabled",
    "system": "notif_system_enabled",
}
SOUND_SETTING = "notif_sound_volume"

DEFAULT_SOUNDS_DIR = Path(__file__).resolve().parent.parent / "ui" / "resources" / "sounds"
GROUP_WINDOW_SECONDS = 5.0

Listener = Callable[..., Any]


class NotificationManager:
    """Desktop notifications with per-type sound, grouping and tray integration."""

    def __init__(
        self,
        *,
        settings_repo: SettingsRepository | None = None,
        message_repo: MessageRepository | None = None,
        tray: Any | None = None,
        sounds_dir: str | Path | None = None,
        group_window_seconds: float = GROUP_WINDOW_SECONDS,
        current_user_id: str | None = None,
    ) -> None:
        self._settings = settings_repo if settings_repo is not None else SettingsRepository()
        self._messages = message_repo if message_repo is not None else MessageRepository()
        self._tray = tray
        self._sounds_dir = Path(sounds_dir) if sounds_dir else DEFAULT_SOUNDS_DIR
        self._group_window = group_window_seconds
        self._user_id = current_user_id
        self._recent: dict[str, dict[str, Any]] = {}
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._sound_effects: dict[str, Any] = {}

    @property
    def tray(self) -> Any | None:
        return self._tray

    @tray.setter
    def tray(self, tray: Any | None) -> None:
        self._tray = tray

    def notify(
        self,
        title: str,
        message: str,
        type: str = "system",
        callback: Listener | None = None,
        friend_id: str | None = None,
    ) -> bool:
        """Show a notification; returns ``False`` when suppressed by config."""
        type = type if type in NOTIFICATION_TYPES else "system"
        if not self.is_enabled(type):
            return False

        final_title, final_message = self._group(friend_id, title, message)
        self._play_sound(type)
        self._show_tray(final_title, final_message, type)

        if callback is not None:
            self._invoke(callback, friend_id, title, message)
        return True

    def is_enabled(self, type: str) -> bool:
        key = ENABLED_SETTING.get(type, ENABLED_SETTING["system"])
        raw = self._settings.get(key)
        if raw is None:
            return True
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def set_enabled(self, type: str, enabled: bool) -> None:
        key = ENABLED_SETTING.get(type, ENABLED_SETTING["system"])
        self._settings.set(key, "1" if enabled else "0")

    def set_volume(self, volume: int) -> None:
        self._settings.set(SOUND_SETTING, str(max(0, min(100, int(volume)))))

    def get_volume(self) -> int:
        try:
            return max(0, min(100, int(self._settings.get(SOUND_SETTING, "70") or 70)))
        except ValueError:
            return 70

    def get_unread_total(self) -> int:
        if self._messages is None:
            return 0
        try:
            return self._messages.get_total_unread(self._get_user_id())
        except Exception:
            return 0

    # --- internals ---------------------------------------------------------

    def _group(self, friend_id: str | None, title: str, message: str) -> tuple[str, str]:
        if not friend_id:
            return title, message
        now = time.monotonic()
        entry = self._recent.get(friend_id)
        if entry is not None and now - entry["ts"] < self._group_window:
            entry["count"] += 1
            entry["ts"] = now
            grouped = (
                f"{entry['count']} novas mensagens de {entry['title']}"
                if entry["count"] > 1
                else message
            )
            return entry["title"], grouped
        self._recent[friend_id] = {
            "title": title,
            "message": message,
            "count": 1,
            "ts": now,
        }
        return title, message

    def _show_tray(self, title: str, message: str, type: str) -> None:
        tray = self._tray
        if tray is None:
            return
        try:
            from PySide6.QtWidgets import QSystemTrayIcon

            if type == "call":
                icon = QSystemTrayIcon.MessageIcon.Critical
            else:
                icon = QSystemTrayIcon.MessageIcon.Information
            tray.showMessage(title, message, icon, 4000)
        except Exception:
            logger.debug("Tray notification unavailable", exc_info=True)

    def _play_sound(self, type: str) -> None:
        if self.get_volume() <= 0:
            return
        filename = SOUND_FILES.get(type, "notify.ogg")
        path = self._sounds_dir / filename
        if not path.exists():
            return
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtMultimedia import QSoundEffect

            effect = self._sound_effects.get(type)
            if effect is None:
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                self._sound_effects[type] = effect
            effect.setVolume(self.get_volume() / 100.0)
            effect.play()
        except Exception:
            logger.debug("Sound playback unavailable", exc_info=True)

    def _invoke(self, callback: Listener, friend_id: str | None, title: str, message: str) -> None:
        try:
            parameters = [
                parameter
                for parameter in inspect.signature(callback).parameters.values()
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            if len(parameters) == 0:
                result = callback()
            elif len(parameters) == 1 and parameters[0].name in {
                "friend_id",
                "peer_id",
                "user_id",
            }:
                result = callback(friend_id)
            else:
                result = callback(title, message)
            if inspect.isawaitable(result):
                try:
                    asyncio.get_running_loop().create_task(result)
                except RuntimeError:
                    result.close()
        except Exception:
            logger.debug("Notification callback failed", exc_info=True)

    def _get_user_id(self) -> str:
        if self._user_id:
            return str(self._user_id)
        from client.storage.repositories import UserRepository

        user = UserRepository().get_current()
        if user is not None and getattr(user, "id", None):
            self._user_id = str(user.id)
            return self._user_id
        return ""


__all__ = [
    "DEFAULT_SOUNDS_DIR",
    "NOTIFICATION_TYPES",
    "NotificationManager",
]
