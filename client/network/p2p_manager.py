from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from client.network.webrtc_session import CONNECTION_TIMEOUT, WebRTCSession, WebRTCSessionError
from config import settings

logger = logging.getLogger(__name__)

Listener = Callable[..., Any]

SIGNALING_EVENT_BY_TYPE = {
    "offer": "signaling_offer",
    "answer": "signaling_answer",
    "ice_candidate": "signaling_ice",
}


class P2PManager:
    """Coordinates WebRTC sessions for a list of peers over a signaling client.

    Emits the following events (subscribe with :meth:`on`):
    ``peer_connected``, ``peer_disconnected``, ``data_channel_open``,
    ``data_channel_message`` and ``connection_failed``.
    """

    def __init__(
        self,
        signaling_client: Any,
        *,
        ice_servers: list[str] | None = None,
        current_user_id: str | None = None,
        max_retries: int = 3,
        connection_timeout: float = CONNECTION_TIMEOUT,
        backoff: float = 1.0,
    ) -> None:
        self._signaling = signaling_client
        self._ice_servers = list(ice_servers if ice_servers is not None else settings.STUN_SERVERS)
        self._user_id = current_user_id
        self._max_retries = max(0, int(max_retries))
        self._connection_timeout = connection_timeout
        self._backoff = max(0.0, float(backoff))

        self._sessions: dict[str, WebRTCSession] = {}
        self._operations: dict[str, Callable[[], Any]] = {}
        self._attempts: dict[str, int] = {}
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._closed = False

        self._handlers = {
            "signaling_offer": self._on_signaling_offer,
            "signaling_answer": self._on_signaling_answer,
            "signaling_ice": self._on_signaling_ice,
        }
        for event, handler in self._handlers.items():
            if hasattr(self._signaling, "on"):
                self._signaling.on(event, handler)

        self.signaling = signaling_client
        self.user_id = current_user_id

    def on(self, event: str, callback: Listener) -> Listener:
        self._listeners[event].append(callback)
        return callback

    def off(self, event: str, callback: Listener) -> None:
        callbacks = self._listeners.get(event, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks:
            self._listeners.pop(event, None)

    async def connect_to_peer(self, peer_id: str) -> WebRTCSession | None:
        """Initiator flow: create a session, open a DataChannel and send an offer."""
        peer_id = str(peer_id)
        existing = self._sessions.get(peer_id)
        if existing is not None and existing.is_open:
            return existing

        session = self._create_session(peer_id)
        self._operations[peer_id] = lambda: self.connect_to_peer(peer_id)
        try:
            offer = await session.create_offer()
            await self._send_signaling(peer_id, "offer", offer)
        except Exception as exc:
            await self._handle_session_error(peer_id, exc)
            return None
        await session.wait_until_open(self._connection_timeout)
        return session

    async def accept_offer(self, peer_id: str, offer: dict[str, Any]) -> WebRTCSession | None:
        """Answerer flow: accept a remote offer and reply with an answer."""
        peer_id = str(peer_id)
        existing = self._sessions.get(peer_id)
        if existing is not None and existing.is_open:
            return existing

        session = self._create_session(peer_id)
        self._operations[peer_id] = lambda: self.accept_offer(peer_id, offer)
        try:
            await session.set_remote_offer(offer)
            answer = await session.create_answer()
            await self._send_signaling(peer_id, "answer", answer)
        except Exception as exc:
            await self._handle_session_error(peer_id, exc)
            return None
        await session.wait_until_open(self._connection_timeout)
        return session

    async def handle_answer(self, peer_id: str, answer: dict[str, Any]) -> None:
        session = self._get_session(peer_id)
        if session is None:
            logger.warning("Received answer for unknown peer %s", peer_id)
            return
        await session.set_remote_answer(answer)

    async def handle_ice_candidate(self, peer_id: str, candidate: dict[str, Any]) -> None:
        session = self._get_session(peer_id)
        if session is None:
            return
        await session.add_ice_candidate(candidate)

    def get_session(self, peer_id: str) -> WebRTCSession | None:
        return self._get_session(peer_id)

    def add_audio_track(self, peer_id: str, track: Any) -> Any:
        session = self._get_session(peer_id)
        if session is None:
            raise WebRTCSessionError(f"No session for peer {peer_id}")
        return session.add_audio_track(track)

    def has_audio_sender(self, peer_id: str) -> bool:
        session = self._get_session(peer_id)
        return bool(session is not None and session.has_audio_sender())

    def on_remote_track(self, peer_id: str, callback: Any) -> None:
        session = self._get_session(peer_id)
        if session is not None:
            session.on_remote_track(callback)

    async def create_renegotiation_offer(self, peer_id: str) -> dict[str, Any]:
        session = self._get_session(peer_id)
        if session is None:
            raise WebRTCSessionError(f"No session for peer {peer_id}")
        return await session.create_offer()

    async def create_renegotiation_answer(
        self, peer_id: str, offer_dict: dict[str, Any]
    ) -> dict[str, Any]:
        session = self._get_session(peer_id)
        if session is None:
            raise WebRTCSessionError(f"No session for peer {peer_id}")
        await session.set_remote_offer(offer_dict)
        return await session.create_answer()

    async def apply_remote_answer(self, peer_id: str, answer_dict: dict[str, Any]) -> None:
        session = self._get_session(peer_id)
        if session is None:
            raise WebRTCSessionError(f"No session for peer {peer_id}")
        await session.set_remote_answer(answer_dict)

    def disconnect_peer(self, peer_id: str) -> None:
        asyncio.ensure_future(self._cleanup(str(peer_id)))

    def get_data_channel(self, peer_id: str) -> Any | None:
        session = self._get_session(peer_id)
        if session is None or not session.is_open:
            return None
        return session.data_channel

    def is_connected(self, peer_id: str) -> bool:
        return self.get_data_channel(peer_id) is not None

    async def send_message(self, peer_id: str, data: str | bytes) -> None:
        channel = self.get_data_channel(peer_id)
        if channel is None:
            raise WebRTCSessionError(f"No open data channel for peer {peer_id}")
        channel.send(data)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for event, handler in self._handlers.items():
            if hasattr(self._signaling, "off"):
                self._signaling.off(event, handler)
        for peer_id in list(self._sessions):
            asyncio.ensure_future(self._cleanup(peer_id))
        self._sessions.clear()
        self._operations.clear()
        self._attempts.clear()
        self._listeners.clear()

    # --- signaling event handlers -------------------------------------------

    async def _on_signaling_offer(self, payload: Any) -> None:
        peer_id = self._peer_from_payload(payload)
        offer = self._data_from_payload(payload)
        if peer_id is None or not isinstance(offer, dict):
            return
        await self.accept_offer(peer_id, offer)

    async def _on_signaling_answer(self, payload: Any) -> None:
        peer_id = self._peer_from_payload(payload)
        answer = self._data_from_payload(payload)
        if peer_id is None or not isinstance(answer, dict):
            return
        await self.handle_answer(peer_id, answer)

    async def _on_signaling_ice(self, payload: Any) -> None:
        peer_id = self._peer_from_payload(payload)
        candidate = self._data_from_payload(payload)
        if peer_id is None or not isinstance(candidate, dict):
            return
        await self.handle_ice_candidate(peer_id, candidate)

    @staticmethod
    def _peer_from_payload(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        peer_id = payload.get("from") or payload.get("sender_id") or payload.get("peer_id")
        return str(peer_id) if peer_id else None

    @staticmethod
    def _data_from_payload(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return None
        return payload.get("data") or payload.get("payload")

    # --- internals ----------------------------------------------------------

    async def _send_signaling(self, peer_id: str, signaling_type: str, data: Any) -> None:
        if self._closed:
            raise WebRTCSessionError("P2P manager is closed")
        if not hasattr(self._signaling, "send"):
            raise WebRTCSessionError("Signaling client is unavailable")
        result = self._signaling.send(
            "signaling", {"to": peer_id, "type": signaling_type, "data": data}
        )
        if inspect.isawaitable(result):
            await result

    def _create_session(self, peer_id: str) -> WebRTCSession:
        session = WebRTCSession(
            ice_servers=self._ice_servers,
            connection_timeout=self._connection_timeout,
            on_open=lambda: self._on_channel_open(peer_id),
            on_close=lambda: self._on_channel_close(peer_id),
            on_message=lambda data: self._on_channel_message(peer_id, data),
            on_error=lambda err: asyncio.ensure_future(self._handle_session_error(peer_id, err)),
        )
        self._sessions[peer_id] = session
        return session

    def _get_session(self, peer_id: str) -> WebRTCSession | None:
        return self._sessions.get(str(peer_id))

    def _on_channel_open(self, peer_id: str) -> None:
        self._attempts.pop(peer_id, None)
        asyncio.ensure_future(self._emit("data_channel_open", peer_id))
        asyncio.ensure_future(self._emit("peer_connected", peer_id))

    def _on_channel_message(self, peer_id: str, data: Any) -> None:
        asyncio.ensure_future(self._emit("data_channel_message", peer_id, data))

    def _on_channel_close(self, peer_id: str) -> None:
        asyncio.ensure_future(self._emit("peer_disconnected", peer_id))

    async def _handle_session_error(self, peer_id: str, error: Exception) -> None:
        peer_id = str(peer_id)
        if peer_id not in self._sessions:
            return
        logger.warning("P2P connection with %s failed: %s", peer_id, error)
        self._attempts[peer_id] = self._attempts.get(peer_id, 0) + 1
        if self._attempts[peer_id] < self._max_retries and not self._closed:
            await self._cleanup(peer_id)
            asyncio.ensure_future(self._retry(peer_id))
            return
        self._attempts.pop(peer_id, None)
        self._operations.pop(peer_id, None)
        await self._cleanup(peer_id)
        await self._emit("connection_failed", peer_id, error)

    async def _retry(self, peer_id: str) -> None:
        await asyncio.sleep(self._backoff)
        if self._closed:
            return
        operation = self._operations.get(peer_id)
        if operation is None:
            return
        try:
            await operation()
        except Exception:
            logger.debug("P2P retry for %s failed", peer_id, exc_info=True)

    async def _cleanup(self, peer_id: str) -> None:
        session = self._sessions.pop(peer_id, None)
        if session is None:
            return
        was_open = session.is_open
        await session.close()
        if was_open:
            await self._emit("peer_disconnected", peer_id)

    async def _emit(self, event: str, *args: Any) -> None:
        for callback in list(self._listeners.get(event, [])):
            try:
                result = self._call_listener(callback, *args)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("P2P event listener failed: %s", event)

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


__all__ = ["P2PManager"]
