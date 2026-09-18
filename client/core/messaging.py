from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from client.storage.models import Message
from client.storage.repositories import MessageRepository, UserRepository

logger = logging.getLogger(__name__)

Listener = Callable[..., Any]

MESSAGE_TYPES = frozenset(
    {
        "message",
        "message_delivered",
        "typing_start",
        "typing_stop",
        "messages_read",
        "key_exchange",
    }
)
TYPING_STOP_DELAY = 2.0


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return _now()


@dataclass
class MessageData:
    msg_id: str = ""
    sender_id: str = ""
    receiver_id: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=_now)
    read: bool = False
    delivered: bool = False
    encrypted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "read": self.read,
            "delivered": self.delivered,
            "encrypted": self.encrypted,
        }


class MessageManager:
    """Handles P2P text messaging over WebRTC DataChannels.

    Emits the following events (subscribe with :meth:`on`):
    ``message_received``, ``message_delivered``, ``typing``,
    ``message_read`` and ``conversation_read``.
    """

    def __init__(
        self,
        p2p_manager: Any,
        user_id: str | Any | None = None,
        *,
        auth_manager: Any | None = None,
        message_repo: MessageRepository | None = None,
        user_repo: UserRepository | None = None,
        current_user_id: str | None = None,
        wait_timeout: float = 15.0,
        key_manager: Any | None = None,
        encryption: Any | None = None,
    ) -> None:
        if current_user_id is not None:
            user_id = current_user_id
        if (
            user_id is not None
            and hasattr(user_id, "get_current_user")
            and not hasattr(user_id, "send_message")
        ):
            auth_manager = auth_manager or user_id
            user_id = None

        self._p2p = p2p_manager
        self._user_id = user_id
        self._auth_manager = auth_manager or getattr(p2p_manager, "auth_manager", None)
        self._message_repo = message_repo if message_repo is not None else MessageRepository()
        self._user_repo = user_repo if user_repo is not None else UserRepository()
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._typing_timers: dict[str, asyncio.TimerHandle] = {}
        self._typing_active: set[str] = set()
        self._wait_timeout = wait_timeout
        self._key_manager = key_manager
        self._encryption = encryption
        self._peer_keys: dict[str, bytes] = {}
        self._sent_keys: set[str] = set()
        self._closed = False

        self._handlers = {
            "data_channel_message": self._on_channel_message,
            "data_channel_open": self._on_channel_open,
            "peer_disconnected": self._on_peer_disconnected,
        }
        for event, handler in self._handlers.items():
            if hasattr(self._p2p, "on"):
                self._p2p.on(event, handler)

        self.p2p = p2p_manager
        self.user_id = user_id

    def on(self, event: str, callback: Listener) -> Listener:
        self._listeners[event].append(callback)
        return callback

    def off(self, event: str, callback: Listener) -> None:
        callbacks = self._listeners.get(event, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks:
            self._listeners.pop(event, None)

    # --- sending -----------------------------------------------------------

    async def send_message(self, friend_id: str, content: str) -> MessageData | None:
        """Send a text message to a peer, connecting first if needed.

        Returns the saved :class:`MessageData` (truthy) or ``None`` on failure.
        """
        friend_id = str(friend_id)
        content = (content or "").strip()
        if not content:
            return None
        user_id = self._get_user_id()

        channel = self._p2p.get_data_channel(friend_id)
        if channel is None:
            await self._p2p.connect_to_peer(friend_id)
            if not await self._wait_channel_open(friend_id):
                return None
            channel = self._p2p.get_data_channel(friend_id)
        if channel is None:
            return None

        timestamp = _now()
        if self._encryption is not None and self._key_manager is not None:
            if friend_id not in self._peer_keys:
                await self._await_peer_key(friend_id)
        encrypted = self._encrypt_content(friend_id, content)
        payload = {
            "type": "message",
            "msg_id": str(uuid.uuid4()),
            "sender_id": user_id,
            "receiver_id": friend_id,
            "content": encrypted if encrypted is not None else content,
            "encrypted": encrypted is not None,
            "timestamp": timestamp.isoformat(),
        }
        try:
            channel.send(json.dumps(payload))
        except Exception:
            logger.warning("Failed to send message to %s", friend_id, exc_info=True)
            return None

        message = self._save_message(
            Message(
                msg_id=payload["msg_id"],
                sender_id=user_id,
                receiver_id=friend_id,
                content=content,
                timestamp=timestamp,
                read=False,
                delivered=False,
                encrypted=encrypted is not None,
            )
        )
        return self._build_data(message)

    async def mark_conversation_read(self, friend_id: str) -> None:
        friend_id = str(friend_id)
        user_id = self._get_user_id()
        unread = self._message_repo.get_unread_from_friend(user_id, friend_id)
        if not unread:
            return
        ids = [message.msg_id for message in unread]
        self._message_repo.mark_read_by_msg_ids(ids)
        if self._p2p.is_connected(friend_id):
            await self._send_json(
                friend_id,
                {
                    "type": "messages_read",
                    "message_ids": ids,
                    "sender_id": user_id,
                },
            )
        await self._emit("conversation_read", friend_id)

    async def notify_typing(self, friend_id: str) -> None:
        """Call on each keystroke; debounces typing_start/typing_stop."""
        friend_id = str(friend_id)
        if not self._p2p.is_connected(friend_id):
            return
        if friend_id not in self._typing_active:
            self._typing_active.add(friend_id)
            await self._send_json(
                friend_id,
                {"type": "typing_start", "sender_id": self._get_user_id()},
            )
        timer = self._typing_timers.get(friend_id)
        if timer is not None:
            timer.cancel()
        self._typing_timers[friend_id] = asyncio.get_running_loop().call_later(
            TYPING_STOP_DELAY,
            lambda: asyncio.ensure_future(self._send_typing_stop(friend_id)),
        )

    async def _send_typing_stop(self, friend_id: str) -> None:
        self._typing_timers.pop(friend_id, None)
        self._typing_active.discard(friend_id)
        if self._p2p.is_connected(friend_id):
            await self._send_json(
                friend_id,
                {"type": "typing_stop", "sender_id": self._get_user_id()},
            )

    # --- reading -----------------------------------------------------------

    def get_conversation(self, friend_id: str, limit: int = 50) -> list[MessageData]:
        rows = self._message_repo.get_conversation(self._get_user_id(), str(friend_id), limit=limit)
        return [self._build_data(row) for row in rows]

    def get_unread_count(self, friend_id: str) -> int:
        return self._message_repo.get_unread_count(self._get_user_id(), str(friend_id))

    def get_last_message(self, friend_id: str) -> MessageData | None:
        row = self._message_repo.get_last_conversation_message(self._get_user_id(), str(friend_id))
        return self._build_data(row) if row is not None else None

    def clear_conversation(self, friend_id: str) -> None:
        self._message_repo.delete_conversation(self._get_user_id(), str(friend_id))

    def cleanup_old_history(self, days: int = 30) -> int:
        cutoff = _now() - timedelta(days=days)
        return self._message_repo.delete_older_than(cutoff)

    # --- incoming ----------------------------------------------------------

    def _on_channel_message(self, peer_id: str, data: Any) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Ignoring invalid DataChannel message")
            return
        if not isinstance(payload, dict):
            return
        msg_type = payload.get("type")
        if msg_type == "message":
            asyncio.ensure_future(self._handle_message(str(peer_id), payload))
        elif msg_type == "message_delivered":
            asyncio.ensure_future(self._handle_delivered(payload))
        elif msg_type in {"typing_start", "typing_stop"}:
            self._handle_typing(str(peer_id), payload)
        elif msg_type == "messages_read":
            asyncio.ensure_future(self._handle_messages_read(str(peer_id), payload))
        elif msg_type == "key_exchange":
            self._handle_key_exchange(str(peer_id), payload)

    async def _handle_message(self, peer_id: str, payload: dict[str, Any]) -> None:
        sender_id = str(payload.get("sender_id") or peer_id)
        if sender_id != peer_id:
            return
        user_id = self._get_user_id()
        receiver_id = str(payload.get("receiver_id") or user_id)
        if receiver_id != user_id:
            return
        msg_id = payload.get("msg_id")
        raw_content = payload.get("content")
        if not msg_id or raw_content is None:
            return
        msg_id = str(msg_id)
        if self._message_repo.get_by_msg_id(msg_id) is not None:
            return

        encrypted = bool(payload.get("encrypted"))
        if encrypted and isinstance(raw_content, dict):
            content = self._decrypt_content(peer_id, raw_content)
            if content is None:
                logger.warning("Dropping undecryptable message from %s", peer_id)
                return
        else:
            content = str(raw_content)

        timestamp = _parse_timestamp(payload.get("timestamp"))
        message = self._save_message(
            Message(
                msg_id=msg_id,
                sender_id=sender_id,
                receiver_id=user_id,
                content=str(content),
                timestamp=timestamp,
                read=False,
                delivered=True,
                encrypted=encrypted,
            )
        )
        data = self._build_data(message)
        await self._emit("message_received", data)
        await self._send_json(
            peer_id,
            {
                "type": "message_delivered",
                "msg_id": msg_id,
                "sender_id": user_id,
            },
        )

    async def _handle_delivered(self, payload: dict[str, Any]) -> None:
        msg_id = payload.get("msg_id")
        if not msg_id:
            return
        self._message_repo.mark_delivered(str(msg_id))
        await self._emit("message_delivered", str(msg_id))

    async def _handle_messages_read(self, peer_id: str, payload: dict[str, Any]) -> None:
        ids = payload.get("message_ids") or []
        if not ids:
            return
        self._message_repo.mark_read_by_msg_ids([str(message_id) for message_id in ids])
        await self._emit("message_read", peer_id)

    def _handle_typing(self, peer_id: str, payload: dict[str, Any]) -> None:
        is_typing = payload.get("type") == "typing_start"
        asyncio.ensure_future(self._emit("typing", peer_id, is_typing))

    def _on_channel_open(self, peer_id: str) -> None:
        asyncio.ensure_future(self._resend_pending(str(peer_id)))
        asyncio.ensure_future(self._send_key_exchange(str(peer_id)))

    def _on_peer_disconnected(self, peer_id: str) -> None:
        peer_id = str(peer_id)
        self._typing_active.discard(peer_id)
        timer = self._typing_timers.pop(peer_id, None)
        if timer is not None:
            timer.cancel()
        self._peer_keys.pop(peer_id, None)
        self._sent_keys.discard(peer_id)

    async def _resend_pending(self, peer_id: str) -> None:
        user_id = self._get_user_id()
        if not self._p2p.is_connected(peer_id):
            return
        pending = [
            message
            for message in self._message_repo.get_undelivered(user_id)
            if message.receiver_id == peer_id
        ]
        for message in pending:
            channel = self._p2p.get_data_channel(peer_id)
            if channel is None:
                break
            payload = {
                "type": "message",
                "msg_id": message.msg_id,
                "sender_id": message.sender_id,
                "receiver_id": message.receiver_id,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
            }
            try:
                channel.send(json.dumps(payload))
            except Exception:
                logger.warning("Failed to resend message to %s", peer_id, exc_info=True)
                break

    # --- encryption --------------------------------------------------------

    async def _send_key_exchange(self, peer_id: str) -> None:
        if self._key_manager is None or peer_id in self._sent_keys:
            return
        try:
            public_key = self._key_manager.export_public_key()
        except Exception:
            return
        self._sent_keys.add(peer_id)
        await self._send_json(
            peer_id,
            {
                "type": "key_exchange",
                "sender_id": self._get_user_id(),
                "public_key": public_key,
            },
        )

    def _handle_key_exchange(self, peer_id: str, payload: dict[str, Any]) -> None:
        key_b64 = payload.get("public_key")
        if not key_b64 or self._key_manager is None:
            return
        try:
            raw = self._key_manager.import_peer_public_key(str(key_b64))
        except Exception:
            logger.warning("Ignoring invalid public key from %s", peer_id)
            return
        self._peer_keys[str(peer_id)] = raw
        if str(peer_id) not in self._sent_keys:
            asyncio.ensure_future(self._send_key_exchange(str(peer_id)))

    async def _await_peer_key(self, friend_id: str, timeout: float = 3.0) -> bool:
        await self._send_key_exchange(friend_id)
        if friend_id in self._peer_keys:
            return True
        deadline = asyncio.get_running_loop().time() + timeout
        while friend_id not in self._peer_keys:
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(0.05)
        return True

    def _encrypt_content(self, friend_id: str, content: str) -> dict[str, Any] | None:
        if self._encryption is None or self._key_manager is None:
            return None
        peer_key = self._peer_keys.get(friend_id)
        if peer_key is None:
            return None
        try:
            private_key = self._key_manager.get_private_key()
        except Exception:
            return None
        if private_key is None:
            return None
        try:
            return self._encryption.encrypt_message(content, peer_key, private_key)
        except Exception:
            logger.warning("Failed to encrypt message for %s", friend_id, exc_info=True)
            return None

    def _decrypt_content(self, peer_id: str, encrypted: dict[str, Any]) -> str | None:
        if self._encryption is None or self._key_manager is None:
            return None
        peer_key = self._peer_keys.get(peer_id)
        if peer_key is None:
            return None
        try:
            private_key = self._key_manager.get_private_key()
        except Exception:
            return None
        if private_key is None:
            return None
        try:
            return self._encryption.decrypt_message(encrypted, private_key, peer_key)
        except Exception:
            logger.warning("Failed to decrypt message from %s", peer_id, exc_info=True)
            return None

    def get_peer_fingerprint(self, friend_id: str) -> str | None:
        from client.security.identity import UserIdentity

        peer_key = self._peer_keys.get(str(friend_id))
        if peer_key is None:
            return None
        return UserIdentity.get_fingerprint(peer_key)

    # --- helpers -----------------------------------------------------------

    async def _wait_channel_open(self, friend_id: str, timeout: float | None = None) -> bool:
        timeout = self._wait_timeout if timeout is None else timeout
        if self._p2p.is_connected(friend_id):
            return True
        opened = asyncio.Event()

        def _on_open(peer: str) -> None:
            if str(peer) == friend_id:
                opened.set()

        self._p2p.on("data_channel_open", _on_open)
        try:
            try:
                await asyncio.wait_for(opened.wait(), timeout=timeout)
            except TimeoutError:
                return False
            return True
        finally:
            self._p2p.off("data_channel_open", _on_open)

    async def _send_json(self, friend_id: str, payload: dict[str, Any]) -> None:
        channel = self._p2p.get_data_channel(friend_id)
        if channel is None:
            return
        try:
            channel.send(json.dumps(payload))
        except Exception:
            logger.warning("Failed to send DataChannel payload to %s", friend_id, exc_info=True)

    def _save_message(self, message: Message) -> Message:
        return self._message_repo.save_message(message)

    @staticmethod
    def _build_data(message: Message) -> MessageData:
        return MessageData(
            msg_id=message.msg_id,
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            content=message.content,
            timestamp=message.timestamp,
            read=message.read,
            delivered=message.delivered,
            encrypted=message.encrypted,
        )

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
        p2p_user_id = getattr(self._p2p, "user_id", None)
        if p2p_user_id:
            self._user_id = str(p2p_user_id)
            self.user_id = self._user_id
            return self._user_id
        raise RuntimeError("No local user is available")

    # --- events ------------------------------------------------------------

    async def _emit(self, event: str, *args: Any) -> None:
        for callback in list(self._listeners.get(event, [])):
            try:
                result = self._call_listener(callback, *args)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Messaging event listener failed: %s", event)

    @staticmethod
    def _call_listener(callback: Listener, *args: Any) -> Any:
        try:
            parameters = [
                parameter
                for parameter in inspect.signature(callback).parameters.values()
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            if len(parameters) == 0:
                return callback()
            if len(parameters) >= len(args):
                return callback(*args)
        except (TypeError, ValueError):
            pass
        return callback(args[0])

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for timer in self._typing_timers.values():
            timer.cancel()
        self._typing_timers.clear()
        self._typing_active.clear()
        self._peer_keys.clear()
        self._sent_keys.clear()
        for event, handler in self._handlers.items():
            if hasattr(self._p2p, "off"):
                self._p2p.off(event, handler)
        self._listeners.clear()


__all__ = ["MESSAGE_TYPES", "MessageData", "MessageManager", "TYPING_STOP_DELAY"]
