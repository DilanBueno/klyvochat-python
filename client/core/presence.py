from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QApplication

from client.storage.repositories import UserRepository

VALID_STATUSES = frozenset({"online", "idle", "dnd", "offline"})
Listener = Callable[[Any], Any]


class PresenceManager(QObject):
    def __init__(
        self,
        signaling_client: Any | str | None = None,
        user_id: str | None = None,
        *,
        current_user_id: str | None = None,
        idle_interval_ms: int = 60_000,
        idle_interval: float | None = None,
        idle_timeout: float = 60.0,
        start_timer: bool = False,
    ) -> None:
        super().__init__()
        if isinstance(signaling_client, str) and user_id is None:
            user_id, signaling_client = signaling_client, None

        if idle_interval is not None:
            idle_interval_ms = int(idle_interval * 1000)

        self._signaling = signaling_client
        self._auth_manager = (
            signaling_client
            if signaling_client is not None and hasattr(signaling_client, "get_current_user")
            else None
        )
        self._user_id = current_user_id or user_id
        self.user_id = self._user_id
        self._user_repo = UserRepository()
        self._status = "online"
        self._status_cache: dict[str, str] = {}
        self._listeners: list[Listener] = []
        self._last_activity = time.monotonic()
        self._auto_idle = False
        self._idle_timeout = idle_timeout
        self._idle_timer = QTimer(self)
        self.timer = self.idle_timer = self._idle_timer
        self._idle_timer.setInterval(idle_interval_ms)
        self._idle_timer.timeout.connect(self._check_idle)
        if hasattr(self._signaling, "on"):
            self._signaling.on("presence_update", self.handle_presence_update)
        self._install_event_filters()
        if start_timer:
            self._idle_timer.start()

    @property
    def current_status(self) -> str:
        return self._status

    @property
    def status_cache(self) -> dict[str, str]:
        return dict(self._status_cache)

    async def set_status(self, status: str) -> str:
        status = status.lower()
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid presence status: {status}")

        self._auto_idle = status == "online"
        self._set_local_status(status)
        if self._signaling is not None:
            result = self._signaling.send("status_update", {"status": status})
            if inspect.isawaitable(result):
                await result
        return status

    async def update_status(self, status: str) -> str:
        return await self.set_status(status)

    def start(self) -> None:
        self._idle_timer.start()

    def stop(self) -> None:
        self._idle_timer.stop()

    def get_status(self) -> str:
        return self._status

    def on_presence_change(self, callback: Listener) -> Listener:
        self._listeners.append(callback)
        return callback

    def off_presence_change(self, callback: Listener) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def get_friend_status(self, friend_id: str) -> str:
        if str(friend_id) == str(self._user_id or ""):
            return self._status
        return self._status_cache.get(str(friend_id), "offline")

    def clear_friend_status(self, friend_id: str) -> None:
        self._status_cache.pop(str(friend_id), None)

    def _get_user_id(self) -> str:
        if self._user_id:
            return str(self._user_id)
        if self._auth_manager is not None:
            current = self._auth_manager.get_current_user()
            if current is not None and getattr(current, "id", None):
                self._user_id = str(current.id)
                self.user_id = self._user_id
                return self._user_id
        user = self._user_repo.get_current()
        if user is not None and getattr(user, "id", None):
            self._user_id = str(user.id)
            self.user_id = self._user_id
            return self._user_id
        signaling_user_id = getattr(self._signaling, "user_id", None)
        if signaling_user_id:
            self._user_id = str(signaling_user_id)
            return self._user_id
        return ""

    def handle_presence_update(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        friend_id = payload.get("friend_id") or payload.get("user_id") or payload.get("id")
        status = payload.get("status")
        if status is None and "online" in payload:
            status = "online" if payload.get("online") else "offline"
        if not friend_id or status not in VALID_STATUSES:
            return
        friend_id = str(friend_id)
        self._status_cache[friend_id] = str(status)
        self._notify_listeners(friend_id, str(status), payload)

    def handle_event(self, event: str | dict[str, Any], payload: Any = None) -> None:
        if isinstance(event, dict):
            data = event
            event = data.get("type", "")
            payload = data.get("payload", data)
        if event == "presence_update":
            self.handle_presence_update(payload)

    def mark_active(self) -> None:
        self._last_activity = time.monotonic()
        if self._auto_idle:
            self._auto_idle = False
            self._set_local_status("online")
            self._queue_status_update("online")

    def eventFilter(self, watched: Any, event: Any) -> bool:
        if event.type() in self._input_event_types():
            self.mark_active()
        return False

    def shutdown(self) -> None:
        self.close()

    def close(self) -> None:
        self._idle_timer.stop()
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeEventFilter(self)
            except RuntimeError:
                pass
            for widget in list(app.allWidgets()):
                try:
                    widget.removeEventFilter(self)
                except RuntimeError:
                    pass
        if hasattr(self._signaling, "off"):
            self._signaling.off("presence_update", self.handle_presence_update)
        self._listeners.clear()

    def _check_idle(self) -> None:
        self._install_event_filters()
        elapsed = time.monotonic() - self._last_activity
        if self._status == "online" and elapsed >= self._idle_timeout:
            self._auto_idle = True
            self._set_local_status("idle")
            self._queue_status_update("idle")
        elif self._auto_idle and elapsed < self._idle_timeout:
            self._auto_idle = False
            self._set_local_status("online")
            self._queue_status_update("online")

    def _set_local_status(self, status: str) -> None:
        self._status = status
        self._notify_listeners(None, status, {"status": status})

    def _queue_status_update(self, status: str) -> None:
        if self._signaling is None:
            return
        result = self._signaling.send("status_update", {"status": status})
        if not inspect.isawaitable(result):
            return
        try:
            asyncio.get_running_loop().create_task(result)
        except RuntimeError:
            result.close()

    def _notify_listeners(self, friend_id: Any, status: Any, payload: Any) -> None:
        for callback in list(self._listeners):
            try:
                result = self._call_listener(callback, friend_id, status, payload)
                if inspect.isawaitable(result):
                    try:
                        asyncio.get_running_loop().create_task(result)
                    except RuntimeError:
                        result.close()
            except Exception:
                continue

    def _call_listener(self, callback: Listener, friend_id: Any, status: Any, payload: Any) -> Any:
        try:
            parameters = list(inspect.signature(callback).parameters.values())
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            if parameters and parameters[-1].kind == parameters[-1].VAR_POSITIONAL:
                return callback(friend_id, status)
            if len(positional) == 1:
                name = positional[0].name
                if name in {"status", "new_status"}:
                    return callback(status)
                if name in {"friend_id", "user_id", "id"}:
                    return callback(friend_id)
                return callback(payload)
            if len(positional) >= 2:
                first, second = positional[:2]
                if first.name in {"status", "new_status"} and second.name in {
                    "friend_id",
                    "user_id",
                    "id",
                }:
                    return callback(status, friend_id)
                return callback(friend_id, status)
        except (TypeError, ValueError):
            pass
        return callback(payload)

    def _install_event_filters(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        try:
            app.installEventFilter(self)
            for widget in list(app.allWidgets()):
                widget.installEventFilter(self)
        except RuntimeError:
            pass

    def _input_event_types(self) -> frozenset[QEvent.Type]:
        return frozenset(
            {
                QEvent.KeyPress,
                QEvent.KeyRelease,
                QEvent.MouseButtonPress,
                QEvent.MouseButtonRelease,
                QEvent.MouseMove,
                QEvent.Wheel,
            }
        )


__all__ = ["PresenceManager", "VALID_STATUSES"]
