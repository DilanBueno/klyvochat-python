from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from client.storage.models import FriendData
from client.storage.repositories import (
    FriendRepository,
    MessageRepository,
    UserRepository,
)

Listener = Callable[[Any], Any]


@dataclass
class FriendRequestData:
    request_id: str
    requester_id: str
    requester_name: str = ""
    username: str = ""
    email: str = ""
    direction: str = "incoming"
    addressee_id: str = ""
    created_at: Any = None

    @property
    def id(self) -> str:
        return self.request_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.request_id,
            "request_id": self.request_id,
            "requester_id": self.requester_id,
            "requester_name": self.requester_name,
            "username": self.username,
            "email": self.email,
            "direction": self.direction,
            "addressee_id": self.addressee_id,
            "created_at": self.created_at,
        }


class FriendManager:
    def __init__(
        self,
        signaling_client: Any,
        user_id: str | Any | None = None,
        presence_manager: Any | None = None,
        *,
        auth_manager: Any | None = None,
        friend_repo: FriendRepository | Any | None = None,
        message_repo: MessageRepository | Any | None = None,
        user_repo: UserRepository | Any | None = None,
        current_user_id: str | None = None,
    ) -> None:
        if current_user_id is not None:
            user_id = current_user_id
        if (
            user_id is not None
            and hasattr(user_id, "get_current_user")
            and not hasattr(user_id, "get_friend_status")
        ):
            auth_manager = auth_manager or user_id
            user_id = None
        if presence_manager is None and hasattr(user_id, "get_friend_status"):
            presence_manager, user_id = user_id, None
        elif (
            presence_manager is not None
            and hasattr(user_id, "get_friend_status")
            and not hasattr(presence_manager, "get_friend_status")
        ):
            user_id, presence_manager = presence_manager, user_id

        self._signaling = signaling_client
        self._user_id = user_id
        self._presence = presence_manager
        self._friend_repo = friend_repo if friend_repo is not None else FriendRepository()
        self._message_repo = message_repo if message_repo is not None else MessageRepository()
        self._user_repo = user_repo if user_repo is not None else UserRepository()
        self._auth_manager = auth_manager or getattr(signaling_client, "auth_manager", None)
        self.signaling = signaling_client
        self.user_id = user_id
        self.presence_manager = presence_manager
        self.friend_repo = self._friend_repo
        self.message_repo = self._message_repo
        self.user_repo = self._user_repo
        self._friend_metadata: dict[str, dict[str, Any]] = {}
        self._pending_requests: dict[str, FriendRequestData] = {}
        self._outgoing_requests: dict[str, FriendRequestData] = {}
        self._pending_presence: dict[str, str] = {}
        self._snapshot_loaded = False
        self._listeners: list[Listener] = []
        self._auto_accept = False
        self._closed = False

        event_handlers = {
            "auth_ok": self._on_auth_ok,
            "friend_request": self._on_friend_request,
            "friend_accept": self._on_friend_accept,
            "friend_reject": self._on_friend_reject,
            "friend_remove": self._on_friend_remove,
            "friend_action_result": self._on_friend_action_result,
        }
        if self._presence is None:
            event_handlers["presence_update"] = self._on_presence_update
        for event, handler in event_handlers.items():
            if hasattr(self._signaling, "on"):
                self._signaling.on(event, handler)
        if self._presence is not None and hasattr(self._presence, "on_presence_change"):
            self._presence.on_presence_change(self._on_presence_change)

    async def send_request(self, email: str) -> Any:
        return await self._send("friend_request", {"email": email.strip()})

    async def _send(self, event_type: str, payload: dict[str, Any]) -> Any:
        if self._closed:
            raise RuntimeError("Friend manager is closed")
        if not hasattr(self._signaling, "send"):
            raise RuntimeError("Signaling client is unavailable")
        result = self._signaling.send(event_type, payload)
        if inspect.isawaitable(result):
            return await result
        return result

    async def accept_request(self, request_id: str) -> Any:
        result = await self._send("friend_accept", {"request_id": str(request_id)})
        self._pending_requests.pop(str(request_id), None)
        return result

    async def reject_request(self, request_id: str) -> Any:
        result = await self._send("friend_reject", {"request_id": str(request_id)})
        self._pending_requests.pop(str(request_id), None)
        return result

    async def remove_friend(self, friend_id: str) -> None:
        friend_id = str(friend_id)
        await self._send("friend_remove", {"friend_id": friend_id})
        self._remove_local_friend(friend_id)

    async def load_friends(self) -> list[FriendData]:
        auth_payload = (
            self._signaling.auth_payload if hasattr(self._signaling, "auth_payload") else None
        )
        if auth_payload:
            self._apply_friend_snapshot(auth_payload.get("friends", []))
        self._snapshot_loaded = True
        self._replay_pending_presence()
        return self.get_friend_list()

    def get_friend_list(self) -> list[FriendData]:
        user_id = self._get_user_id()
        friends = self._friend_repo.get_friends(user_id)
        friend_ids = {
            str(friend.get("friend_id") if isinstance(friend, dict) else friend.friend_id)
            for friend in friends
        }
        friend_ids.update(self._friend_metadata)
        result = [self._get_friend_data(friend_id) for friend_id in sorted(friend_ids)]
        return [friend for friend in result if friend is not None]

    def get_pending_requests(self) -> list[FriendRequestData]:
        return list(self._pending_requests.values())

    def get_outgoing_requests(self) -> list[FriendRequestData]:
        return list(self._outgoing_requests.values())

    def set_auto_accept(self, enabled: bool) -> None:
        self._auto_accept = bool(enabled)

    def on_friend_update(self, callback: Listener) -> Listener:
        self._listeners.append(callback)
        return callback

    def off_friend_update(self, callback: Listener) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def handle_event(self, event: str, payload: Any) -> None:
        handlers = {
            "auth_ok": self._on_auth_ok,
            "friend_request": self._on_friend_request,
            "friend_accept": self._on_friend_accept,
            "friend_reject": self._on_friend_reject,
            "friend_remove": self._on_friend_remove,
            "friend_action_result": self._on_friend_action_result,
            "presence_update": self._on_presence_update,
        }
        handler = handlers.get(event)
        if handler is not None:
            handler(payload)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        handlers = {
            "auth_ok": self._on_auth_ok,
            "friend_request": self._on_friend_request,
            "friend_accept": self._on_friend_accept,
            "friend_reject": self._on_friend_reject,
            "friend_remove": self._on_friend_remove,
            "friend_action_result": self._on_friend_action_result,
            "presence_update": self._on_presence_update,
        }
        for event, handler in handlers.items():
            if hasattr(self._signaling, "off"):
                self._signaling.off(event, handler)
        if self._presence is not None and hasattr(self._presence, "off_presence_change"):
            self._presence.off_presence_change(self._on_presence_change)
        self._listeners.clear()

    def delete_conversation(self, friend_id: str) -> None:
        self._message_repo.delete_conversation(self._get_user_id(), str(friend_id))

    def _on_auth_ok(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        self._apply_friend_snapshot(payload.get("friends", []))
        self._apply_pending_requests(payload.get("pending_requests", []))
        self._snapshot_loaded = True
        self._replay_pending_presence()
        self._notify_listeners(self.get_friend_list(), "auth_ok")

    def _on_friend_request(self, payload: Any) -> None:
        request = self._request_from_payload(payload)
        if request is None:
            return
        if request.direction == "incoming":
            self._pending_requests[request.request_id] = request
            if self._auto_accept:
                asyncio.ensure_future(self.accept_request(request.request_id))
        else:
            self._outgoing_requests[request.request_id] = request
        self._notify_listeners(request, "friend_request")

    def _on_friend_accept(self, payload: Any) -> None:
        data = self._extract_friend(payload)
        if not data and isinstance(payload, dict):
            requester_id = payload.get("requester_id")
            addressee_id = payload.get("addressee_id")
            user_id = self._get_user_id()
            if requester_id == user_id and addressee_id:
                data = dict(payload)
                data["id"] = addressee_id
            elif addressee_id == user_id and requester_id:
                data = dict(payload)
                data["id"] = requester_id
        if not data:
            return
        friend = self._normalize_friend(data)
        if friend is None:
            return
        self._upsert_friend_data(friend)
        self._outgoing_requests = {
            request_id: request
            for request_id, request in self._outgoing_requests.items()
            if request.addressee_id != friend.friend_id
        }
        self._notify_listeners(friend, "friend_accept")

    def _on_friend_reject(self, payload: Any) -> None:
        data = payload if isinstance(payload, dict) else {}
        request_id = data.get("id") or data.get("request_id")
        requester_id = data.get("requester_id")
        if request_id:
            self._pending_requests.pop(str(request_id), None)
            self._outgoing_requests.pop(str(request_id), None)
        elif requester_id:
            self._outgoing_requests = {
                key: request
                for key, request in self._outgoing_requests.items()
                if request.requester_id != str(requester_id)
            }
        self._notify_listeners(data, "friend_reject")

    def _on_friend_remove(self, payload: Any) -> None:
        data = payload if isinstance(payload, dict) else {}
        friend_id = data.get("friend_id") or data.get("id") or data.get("user_id")
        if not friend_id:
            return
        self._remove_local_friend(str(friend_id))
        self._notify_listeners(str(friend_id), "friend_remove")

    def _on_friend_action_result(self, payload: Any) -> None:
        if not isinstance(payload, dict) or not payload.get("ok"):
            return
        action = payload.get("action")
        request = payload.get("request")
        if action in {"request", "send_request"} and isinstance(request, dict):
            normalized = self._request_from_payload(request)
            if normalized is not None:
                if normalized.direction == "outgoing":
                    self._outgoing_requests[normalized.request_id] = normalized
                else:
                    self._pending_requests[normalized.request_id] = normalized
        elif action in {"accept", "reject"} and request:
            request_id = str(request.get("id") or request.get("request_id") or "")
            self._pending_requests.pop(request_id, None)
            self._outgoing_requests.pop(request_id, None)
        elif action == "remove":
            friend_id = payload.get("friend_id")
            if friend_id:
                self._remove_local_friend(str(friend_id))

    def _on_presence_update(self, payload: Any) -> None:
        data = payload if isinstance(payload, dict) else {}
        friend_id = data.get("friend_id") or data.get("user_id") or data.get("id")
        status = data.get("status")
        if status is None and "online" in data:
            status = "online" if data.get("online") else "offline"
        if not friend_id or not status:
            return
        friend_id = str(friend_id)
        status = str(status)
        if not self._snapshot_loaded:
            self._pending_presence[friend_id] = status
            return
        if (
            self._get_repo_friend(self._get_user_id(), friend_id) is None
            and friend_id not in self._friend_metadata
        ):
            return
        self._set_friend_status(friend_id, status)

    def _on_presence_change(self, friend_id: Any, status: Any) -> None:
        if friend_id is None:
            return
        friend_id = str(friend_id)
        status = str(status)
        if not self._snapshot_loaded:
            self._pending_presence[friend_id] = status
            return
        if (
            self._get_repo_friend(self._get_user_id(), friend_id) is None
            and friend_id not in self._friend_metadata
        ):
            return
        self._set_friend_status(friend_id, status)

    def _apply_friend_snapshot(self, friends: Any) -> None:
        if not isinstance(friends, list):
            return
        for raw_friend in friends:
            friend = self._normalize_friend(raw_friend)
            if friend is not None:
                self._upsert_friend_data(friend)

    def _apply_pending_requests(self, requests: Any) -> None:
        if not isinstance(requests, list):
            return
        for raw_request in requests:
            request = self._request_from_payload(raw_request)
            if request is None:
                continue
            if request.direction == "incoming":
                self._pending_requests[request.request_id] = request
            else:
                self._outgoing_requests[request.request_id] = request

    def _request_from_payload(self, payload: Any) -> FriendRequestData | None:
        if not isinstance(payload, dict):
            return None
        request = payload.get("request") or payload
        if not isinstance(request, dict):
            return None
        user = payload.get("user") or request.get("user")
        if not isinstance(user, dict):
            user = {}
        request_id = request.get("id") or request.get("request_id")
        requester_id = request.get("requester_id") or user.get("id")
        addressee_id = request.get("addressee_id")
        if not request_id or not requester_id:
            return None
        user_id = self._get_user_id()
        direction = request.get("direction")
        if not direction:
            direction = "incoming" if str(addressee_id) == str(user_id) else "outgoing"
        return FriendRequestData(
            request_id=str(request_id),
            requester_id=str(requester_id),
            requester_name=user.get("username") or user.get("name") or requester_id,
            username=user.get("username", ""),
            email=user.get("email", ""),
            direction=direction,
            addressee_id=str(addressee_id or ""),
            created_at=request.get("created_at"),
        )

    def _normalize_friend(self, raw: Any) -> FriendData | None:
        if isinstance(raw, FriendData):
            return raw
        if not isinstance(raw, dict):
            return None
        data = raw.get("friend") or raw.get("user") or raw
        if not isinstance(data, dict):
            return None
        friend_id = data.get("friend_id") or data.get("id") or data.get("user_id")
        if not friend_id:
            return None
        friend_id = str(friend_id)
        username = data.get("username") or data.get("name") or ""
        name = data.get("name") or data.get("nickname") or username or friend_id
        email = data.get("email", "")
        status = data.get("status") or "offline"
        return FriendData(
            id=data.get("id") or friend_id,
            friend_id=friend_id,
            user_id=data.get("user_id") or friend_id,
            username=username,
            name=name,
            email=email,
            status=status,
            nickname=data.get("nickname"),
            added_at=data.get("added_at"),
        )

    def _upsert_friend_data(self, friend: FriendData) -> None:
        user_id = self._get_user_id()
        self._upsert_friend(
            user_id,
            friend.friend_id,
            nickname=friend.nickname,
            username=friend.username,
            email=friend.email,
            status=friend.status,
        )
        self._friend_metadata[friend.friend_id] = {
            "id": friend.id,
            "friend_id": friend.friend_id,
            "user_id": friend.user_id,
            "username": friend.username,
            "name": friend.name,
            "email": friend.email,
            "status": friend.status,
            "added_at": friend.added_at,
            "nickname": friend.nickname,
        }

    def _remove_local_friend(self, friend_id: str) -> None:
        user_id = self._get_user_id()
        removed = self._get_friend_data(friend_id)
        self._friend_repo.remove_friend(user_id, friend_id)
        self._friend_metadata.pop(friend_id, None)
        self._pending_presence.pop(friend_id, None)
        if self._presence is not None and hasattr(self._presence, "clear_friend_status"):
            self._presence.clear_friend_status(friend_id)
        self._notify_listeners(removed or friend_id, "friend_remove")

    def _set_friend_status(self, friend_id: str, status: str) -> None:
        metadata = self._friend_metadata.setdefault(friend_id, {})
        metadata["status"] = status
        friend = self._get_friend_data(friend_id)
        if friend is not None:
            self._notify_listeners(friend, "presence_update")

    def _replay_pending_presence(self) -> None:
        for friend_id, status in list(self._pending_presence.items()):
            if (
                self._get_repo_friend(self._get_user_id(), friend_id) is not None
                or friend_id in self._friend_metadata
            ):
                self._set_friend_status(friend_id, status)
                self._pending_presence.pop(friend_id, None)

    def _get_friend_data(self, friend_id: str) -> FriendData | None:
        friend_id = str(friend_id)
        row = self._get_repo_friend(self._get_user_id(), friend_id)
        metadata = self._friend_metadata.get(friend_id, {})
        if row is None and not metadata:
            return None

        row_values = {}
        if row is not None:
            row_values = {
                "id": getattr(row, "friend_id", None),
                "user_id": getattr(row, "friend_id", None),
                "username": getattr(row, "username", None),
                "email": getattr(row, "email", None),
                "status": getattr(row, "status", "offline"),
                "nickname": getattr(row, "nickname", None),
                "added_at": getattr(row, "added_at", None),
            }

        status = metadata.get("status") or row_values.get("status") or "offline"
        if self._presence is not None:
            try:
                status = self._presence.get_friend_status(friend_id) or status
            except Exception:
                pass

        username = metadata.get("username") or row_values.get("username") or ""
        name = (
            metadata.get("name")
            or row_values.get("username")
            or row_values.get("nickname")
            or username
            or friend_id
        )
        email = metadata.get("email") or row_values.get("email") or ""
        return FriendData(
            id=metadata.get("id") or row_values.get("id") or friend_id,
            friend_id=friend_id,
            user_id=metadata.get("user_id") or row_values.get("user_id") or friend_id,
            username=username,
            name=name,
            email=email,
            status=status,
            nickname=metadata.get("nickname") or row_values.get("nickname"),
            added_at=metadata.get("added_at") or row_values.get("added_at"),
        )

    def _upsert_friend(
        self,
        user_id: str,
        friend_id: str,
        nickname: str | None = None,
        username: str | None = None,
        email: str | None = None,
        status: str | None = None,
    ) -> Any:
        if hasattr(self._friend_repo, "upsert_friend"):
            return self._friend_repo.upsert_friend(
                user_id,
                friend_id,
                nickname=nickname,
                username=username,
                email=email,
                status=status,
            )
        return self._friend_repo.add_friend(user_id, friend_id, nickname=nickname)

    def _extract_friend(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        data = payload.get("friend") or payload.get("user") or payload
        return data if isinstance(data, dict) else {}

    def _get_repo_friend(self, user_id: str, friend_id: str) -> Any:
        if not hasattr(self._friend_repo, "get_friend"):
            return None
        return self._friend_repo.get_friend(user_id, friend_id)

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
            self.user_id = self._user_id
            return self._user_id
        raise RuntimeError("No local user is available")

    def _notify_listeners(self, value: Any, event: str) -> None:
        for callback in list(self._listeners):
            try:
                if event == "friend_request" or self._listener_wants_single(callback):
                    update_value = value
                else:
                    update_value = self.get_friend_list()
                result = self._call_listener(callback, update_value, event)
                if inspect.isawaitable(result):
                    self._schedule(result)
            except Exception:
                continue

    def _listener_wants_single(self, callback: Listener) -> bool:
        try:
            parameters = list(inspect.signature(callback).parameters.values())
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            if not positional:
                return False
            return positional[0].name in {"friend", "friend_data", "update", "request"}
        except (TypeError, ValueError):
            return False

    def _call_listener(self, callback: Listener, value: Any, event: str) -> Any:
        try:
            parameters = list(inspect.signature(callback).parameters.values())
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            if len(positional) == 0:
                return callback()
            if len(positional) >= 2:
                return callback(value, event)
        except (TypeError, ValueError):
            pass
        return callback(value)

    def _schedule(self, awaitable: Awaitable[Any]) -> None:
        try:
            asyncio.get_running_loop().create_task(awaitable)
        except RuntimeError:
            awaitable.close()


__all__ = ["FriendManager", "FriendRequestData"]
