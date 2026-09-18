from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

from aiortc import (
    RTCConfiguration,
    RTCIceCandidate,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_ICE_SERVERS = ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]
CONNECTION_TIMEOUT = 10.0

Listener = Callable[..., Any]


class WebRTCSessionError(Exception):
    """Raised when a WebRTC operation fails."""


def _parse_ice_candidate(
    sdp: str, sdp_mid: str | None = None, sdp_mline_index: int | None = None
) -> RTCIceCandidate:
    """Parse an SDP candidate line into an :class:`RTCIceCandidate`."""
    parts = sdp.strip().split()
    if not parts:
        raise WebRTCSessionError("Empty ICE candidate")
    if parts[0].startswith("a="):
        parts[0] = parts[0][2:]
    if parts[0].startswith("candidate:"):
        parts[0] = parts[0][len("candidate:") :]
    foundation = parts[0]
    component = int(parts[1])
    protocol = parts[2]
    priority = int(parts[3])
    ip = parts[4]
    port = int(parts[5])
    type_ = None
    related_address: str | None = None
    related_port: int | None = None
    tcp_type: str | None = None
    index = 6
    while index < len(parts):
        key = parts[index]
        if key == "typ" and index + 1 < len(parts):
            type_ = parts[index + 1]
            index += 2
        elif key in {"raddr", "rport", "tcpType"} and index + 1 < len(parts):
            value = parts[index + 1]
            if key == "raddr":
                related_address = value
            elif key == "rport":
                related_port = int(value)
            else:
                tcp_type = value
            index += 2
        else:
            index += 1
    if not type_:
        raise WebRTCSessionError("ICE candidate is missing its type")
    return RTCIceCandidate(
        component=component,
        foundation=foundation,
        ip=ip,
        port=port,
        priority=priority,
        protocol=protocol,
        type=type_,
        relatedAddress=related_address,
        relatedPort=related_port,
        sdpMid=sdp_mid,
        sdpMLineIndex=sdp_mline_index,
        tcpType=tcp_type,
    )


class WebRTCSession:
    """Thin, friendly wrapper around :class:`aiortc.RTCPeerConnection`.

    SDP offers/answers and ICE candidates are exchanged as JSON-compatible
    dicts (never raw binary).
    """

    def __init__(
        self,
        *,
        ice_servers: list[str] | None = None,
        connection_timeout: float = CONNECTION_TIMEOUT,
        on_open: Listener | None = None,
        on_close: Listener | None = None,
        on_message: Listener | None = None,
        on_error: Listener | None = None,
    ) -> None:
        if ice_servers is None:
            servers = list(settings.STUN_SERVERS)
        else:
            servers = list(ice_servers)
        if not servers:
            servers = list(DEFAULT_ICE_SERVERS)
        self._ice_servers = servers
        self._connection_timeout = connection_timeout
        self._on_open = on_open
        self._on_close = on_close
        self._on_message = on_message
        self._on_error = on_error

        self._pc: RTCPeerConnection | None = None
        self._data_channel: Any = None
        self._audio_sender: Any = None
        self._on_remote_track: Listener | None = None
        self._open_fired = False
        self._closed = False
        self._timeout_handle: asyncio.TimerHandle | None = None

    @property
    def is_open(self) -> bool:
        return self._data_channel is not None and self._data_channel.readyState == "open"

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def connection_state(self) -> str:
        if self._pc is None:
            return "new"
        return self._pc.connectionState

    @property
    def ice_connection_state(self) -> str:
        if self._pc is None:
            return "new"
        return self._pc.iceConnectionState

    @property
    def data_channel(self) -> Any | None:
        return self._data_channel

    def _ensure_peer_connection(self) -> RTCPeerConnection:
        if self._closed:
            raise WebRTCSessionError("Session is closed")
        if self._pc is None:
            configuration = RTCConfiguration(iceServers=[RTCIceServer(urls=self._ice_servers)])
            self._pc = RTCPeerConnection(configuration)
            self._pc.add_listener("connectionstatechange", self._on_connection_state_change)
            self._pc.add_listener("iceconnectionstatechange", self._on_ice_connection_state_change)
            self._pc.add_listener("datachannel", self._on_remote_data_channel)
            self._pc.add_listener("track", self._on_track)
        return self._pc

    def on_remote_track(self, callback: Listener | None) -> None:
        """Register a callback invoked with each remote media track."""
        self._on_remote_track = callback

    def add_audio_track(self, track: Any) -> Any:
        """Add an audio track to the session (only once)."""
        if self._audio_sender is not None:
            return self._audio_sender
        pc = self._ensure_peer_connection()
        self._audio_sender = pc.addTrack(track)
        return self._audio_sender

    def has_audio_sender(self) -> bool:
        return self._audio_sender is not None

    def _on_track(self, track: Any) -> None:
        self._notify(self._on_remote_track, track)

    def create_data_channel(self, label: str = "klyvochat") -> Any:
        """Create (and remember) the local DataChannel for messaging."""
        if self._data_channel is not None:
            return self._data_channel
        pc = self._ensure_peer_connection()
        channel = pc.createDataChannel(label)
        self._bind_data_channel(channel)
        return channel

    def _bind_data_channel(self, channel: Any) -> None:
        channel.add_listener("open", self._on_channel_open)
        channel.add_listener("close", self._on_channel_close)
        channel.add_listener("message", self._on_channel_message)
        self._data_channel = channel
        if channel.readyState == "open":
            self._on_channel_open()

    def _on_remote_data_channel(self, channel: Any) -> None:
        self._bind_data_channel(channel)

    async def create_offer(self) -> dict[str, Any]:
        """Create the local SDP offer and return it as a JSON dict."""
        pc = self._ensure_peer_connection()
        if self._data_channel is None:
            self.create_data_channel()
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        self._arm_connection_timer()
        return self._serialize_description(pc.localDescription)

    async def set_remote_offer(self, offer_dict: dict[str, Any]) -> None:
        pc = self._ensure_peer_connection()
        await pc.setRemoteDescription(self._deserialize_description(offer_dict))

    async def create_answer(self) -> dict[str, Any]:
        pc = self._ensure_peer_connection()
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        self._arm_connection_timer()
        return self._serialize_description(pc.localDescription)

    async def set_remote_answer(self, answer_dict: dict[str, Any]) -> None:
        pc = self._ensure_peer_connection()
        await pc.setRemoteDescription(self._deserialize_description(answer_dict))

    async def add_ice_candidate(self, candidate_dict: dict[str, Any]) -> None:
        candidate = self._deserialize_candidate(candidate_dict)
        if candidate is None:
            return
        pc = self._ensure_peer_connection()
        await pc.addIceCandidate(candidate)

    async def send(self, data: str | bytes) -> None:
        if self._data_channel is None or self._data_channel.readyState != "open":
            raise WebRTCSessionError("Data channel is not open")
        self._data_channel.send(data)

    async def close(self) -> None:
        self._closed = True
        self._cancel_connection_timer()
        channel = self._data_channel
        self._data_channel = None
        if channel is not None and channel.readyState not in ("closed", "closing"):
            try:
                channel.close()
            except Exception:
                logger.debug("Error closing data channel", exc_info=True)
        pc = self._pc
        self._pc = None
        if pc is not None:
            try:
                await pc.close()
            except Exception:
                logger.debug("Error closing peer connection", exc_info=True)

    async def wait_until_open(self, timeout: float | None = None) -> bool:
        """Block until the DataChannel is open, or ``False`` on timeout."""
        timeout = timeout if timeout is not None else self._connection_timeout
        if self.is_open:
            return True
        opened = asyncio.Event()

        def on_open() -> None:
            opened.set()

        original = self._on_open
        self._on_open = lambda: (original(), on_open()) if original else on_open()
        try:
            try:
                await asyncio.wait_for(opened.wait(), timeout=timeout)
            except TimeoutError:
                return False
            return self.is_open
        finally:
            self._on_open = original

    def _arm_connection_timer(self) -> None:
        self._cancel_connection_timer()
        loop = asyncio.get_running_loop()

        def _on_timeout() -> None:
            if self.is_open or self._closed:
                return
            self._notify_error(WebRTCSessionError("Connection timed out"))
            asyncio.ensure_future(self.close())

        self._timeout_handle = loop.call_later(self._connection_timeout, _on_timeout)

    def _cancel_connection_timer(self) -> None:
        if self._timeout_handle is not None:
            self._timeout_handle.cancel()
            self._timeout_handle = None

    def _on_connection_state_change(self) -> None:
        state = self.connection_state
        logger.debug("WebRTC connection state changed to %s", state)
        if state == "connected":
            self._cancel_connection_timer()
        elif state in {"failed", "closed"} and not self.is_open:
            self._notify_error(WebRTCSessionError(f"Connection failed ({state})"))
            asyncio.ensure_future(self.close())

    def _on_ice_connection_state_change(self) -> None:
        state = self.ice_connection_state
        logger.debug("WebRTC ICE connection state changed to %s", state)
        if state in {"failed", "disconnected"} and not self.is_open:
            self._notify_error(WebRTCSessionError(f"ICE connection failed ({state})"))
            asyncio.ensure_future(self.close())

    def _on_channel_open(self) -> None:
        if self._open_fired:
            return
        self._open_fired = True
        self._cancel_connection_timer()
        self._notify(self._on_open)

    def _on_channel_close(self) -> None:
        self._cancel_connection_timer()
        self._notify(self._on_close)

    def _on_channel_message(self, message: str | bytes) -> None:
        self._notify(self._on_message, message)

    def _notify_error(self, error: Exception) -> None:
        self._notify(self._on_error, error)

    def _notify(self, callback: Listener | None, *args: Any) -> None:
        if callback is None:
            return
        try:
            result = callback(*args)
            if inspect.isawaitable(result):
                asyncio.ensure_future(result)
        except Exception:
            logger.exception("WebRTC callback failed")

    @staticmethod
    def _serialize_description(description: Any) -> dict[str, Any]:
        if description is None:
            raise WebRTCSessionError("No local description is available")
        return {"type": description.type, "sdp": description.sdp}

    @staticmethod
    def _deserialize_description(description_dict: Any) -> RTCSessionDescription:
        if isinstance(description_dict, RTCSessionDescription):
            return description_dict
        if not isinstance(description_dict, dict):
            raise WebRTCSessionError("Invalid SDP description payload")
        sdp = description_dict.get("sdp")
        desc_type = description_dict.get("type")
        if not isinstance(sdp, str) or not sdp or desc_type not in {"offer", "answer"}:
            raise WebRTCSessionError("Invalid SDP description payload")
        return RTCSessionDescription(sdp=sdp, type=desc_type)

    @staticmethod
    def _deserialize_candidate(candidate_dict: Any) -> RTCIceCandidate | None:
        if isinstance(candidate_dict, RTCIceCandidate):
            return candidate_dict
        if not isinstance(candidate_dict, dict):
            return None
        sdp = candidate_dict.get("candidate") or candidate_dict.get("sdp")
        if not isinstance(sdp, str) or not sdp:
            return None
        sdp_mid = candidate_dict.get("sdpMid") or candidate_dict.get("sdp_mid")
        mline = candidate_dict.get("sdpMLineIndex")
        mline = mline if mline is not None else candidate_dict.get("sdp_mline_index")
        try:
            return _parse_ice_candidate(sdp, sdp_mid, int(mline) if mline is not None else None)
        except Exception:
            logger.warning("Ignoring unparseable ICE candidate", exc_info=True)
            return None


__all__ = [
    "CONNECTION_TIMEOUT",
    "DEFAULT_ICE_SERVERS",
    "WebRTCSession",
    "WebRTCSessionError",
    "_parse_ice_candidate",
]
