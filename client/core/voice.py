from __future__ import annotations

import asyncio
import collections
import fractions
import inspect
import json
import logging
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import av
import numpy as np
from aiortc.mediastreams import MediaStreamError, MediaStreamTrack

from client.storage.repositories import UserRepository

try:
    import sounddevice as _sounddevice
except Exception:  # pragma: no cover - optional dependency at runtime
    _sounddevice = None

logger = logging.getLogger(__name__)

AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 1
AUDIO_BLOCK_SIZE = 960  # 20ms at 48kHz
AUDIO_DTYPE = "int16"
VAD_THRESHOLD = 0.01

CALL_IDLE = "idle"
CALL_RINGING_OUT = "ringing_out"
CALL_RINGING_IN = "ringing_in"
CALL_CONNECTING = "connecting"
CALL_ACTIVE = "active"
CALL_ENDED = "ended"

CALL_STATES = frozenset(
    {CALL_IDLE, CALL_RINGING_OUT, CALL_RINGING_IN, CALL_CONNECTING, CALL_ACTIVE, CALL_ENDED}
)
CALL_TYPES = frozenset({"call_invite", "call_answer", "call_reject", "call_end", "call_state"})

Listener = Callable[..., Any]


class CallError(Exception):
    """Raised when a call operation is invalid."""


class AudioDeviceError(Exception):
    """Raised when an audio device cannot be opened."""


def frame_energy(frame: np.ndarray) -> float:
    """Return the normalized RMS energy (0.0-1.0) of an int16 audio frame."""
    if frame is None or frame.size == 0:
        return 0.0
    data = np.asarray(frame, dtype=np.float64)
    rms = float(np.sqrt(np.mean(np.square(data)))) / 32767.0
    return max(0.0, min(1.0, rms))


def is_speech(frame: np.ndarray, threshold: float = VAD_THRESHOLD) -> bool:
    return frame_energy(frame) >= threshold


def normalize_frame(frame: np.ndarray, block_size: int = AUDIO_BLOCK_SIZE) -> np.ndarray:
    """Normalize an audio frame to int16 mono with shape ``(1, block_size)``."""
    data = np.asarray(frame)
    if data.dtype != np.int16:
        data = np.clip(data * 32767.0, -32768.0, 32767.0).astype(np.int16)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    elif data.shape[0] == block_size and data.shape[1] == 1:
        data = data.T
    elif data.shape[1] == 1 and data.shape[0] != 1:
        data = data.T
    data = data.astype(np.int16)
    if data.shape[1] < block_size:
        pad = np.zeros((1, block_size - data.shape[1]), dtype=np.int16)
        data = np.concatenate([data, pad], axis=1)
    elif data.shape[1] > block_size:
        data = data[:, :block_size]
    return data


class AudioStream:
    """Captures and plays audio through ``sounddevice`` (48kHz, mono, int16)."""

    def __init__(
        self,
        *,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
        block_size: int = AUDIO_BLOCK_SIZE,
        dtype: str = AUDIO_DTYPE,
        sounddevice: Any | None = None,
    ) -> None:
        self._sd = sounddevice if sounddevice is not None else _sounddevice
        self._sample_rate = sample_rate
        self._channels = channels
        self._block_size = block_size
        self._dtype = dtype
        self._capture_stream: Any = None
        self._playback_stream: Any = None
        self._capture_queue: collections.deque[np.ndarray] = collections.deque(maxlen=60)
        self._capture_event = threading.Event()
        self._playback_queue: collections.deque[np.ndarray] = collections.deque(maxlen=400)
        self._listeners: list[Listener] = []
        self._last_energy = 0.0

    @property
    def block_size(self) -> int:
        return self._block_size

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def list_devices(self) -> list[dict[str, Any]]:
        if self._sd is None:
            return []
        try:
            devices = self._sd.query_devices()
        except Exception:
            return []
        defaults: set[int] = set()
        try:
            defaults.add(int(self._sd.default.device[0]))
        except Exception:
            pass
        result = []
        for index, device in enumerate(devices):
            name = (
                getattr(device, "name", None)
                or (device.get("name") if isinstance(device, dict) else None)
                or str(index)
            )
            result.append(
                {
                    "id": index,
                    "name": name,
                    "inputs": int(getattr(device, "max_input_channels", 0) or 0),
                    "outputs": int(getattr(device, "max_output_channels", 0) or 0),
                    "default": index in defaults,
                }
            )
        return result

    def _input_callback(self, indata, frames: int, time_info, status) -> None:
        data = np.asarray(indata, dtype=self._dtype)
        if self._channels == 1 and data.ndim == 2:
            data = data[:, :1].T
        elif data.ndim == 2:
            data = data.T
        frame = normalize_frame(data, self._block_size)
        self._capture_queue.append(frame)
        self._capture_event.set()
        self._last_energy = frame_energy(frame)

    def start_capture(self, device_id: int | None = None) -> None:
        if self._capture_stream is not None or self._sd is None:
            return
        try:
            stream = self._sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                blocksize=self._block_size,
                device=device_id,
                callback=self._input_callback,
            )
            stream.start()
            self._capture_stream = stream
        except Exception as exc:
            raise AudioDeviceError(f"Failed to open audio input: {exc}") from exc

    def stop_capture(self) -> None:
        if self._capture_stream is not None:
            try:
                self._capture_stream.stop()
                self._capture_stream.close()
            except Exception:
                logger.debug("Error closing capture stream", exc_info=True)
            self._capture_stream = None
        self._capture_queue.clear()

    def _output_callback(self, outdata, frames: int, time_info, status) -> None:
        if self._playback_queue:
            data = self._playback_queue.popleft()  # (1, block_size) int16
            out = data.T
            if out.shape[0] < frames:
                out = np.concatenate(
                    [
                        out,
                        np.zeros((frames - out.shape[0], out.shape[1]), dtype=out.dtype),
                    ]
                )
            outdata[:] = out[:frames]
        else:
            outdata.fill(0)

    def start_playback(self, device_id: int | None = None) -> None:
        if self._playback_stream is not None or self._sd is None:
            return
        try:
            stream = self._sd.OutputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype=self._dtype,
                blocksize=self._block_size,
                device=device_id,
                callback=self._output_callback,
            )
            stream.start()
            self._playback_stream = stream
        except Exception as exc:
            raise AudioDeviceError(f"Failed to open audio output: {exc}") from exc

    def stop_playback(self) -> None:
        if self._playback_stream is not None:
            try:
                self._playback_stream.stop()
                self._playback_stream.close()
            except Exception:
                logger.debug("Error closing playback stream", exc_info=True)
            self._playback_stream = None
        self._playback_queue.clear()

    def play_frame(self, frame: np.ndarray) -> None:
        self._playback_queue.append(normalize_frame(frame, self._block_size))

    def get_captured_frame(self) -> np.ndarray | None:
        if self._capture_queue:
            return self._capture_queue.popleft()
        return None

    def get_energy(self) -> float:
        return self._last_energy

    def on_audio_data(self, callback: Listener) -> Listener:
        self._listeners.append(callback)
        return callback

    def close(self) -> None:
        self.stop_capture()
        self.stop_playback()
        self._listeners.clear()


class AudioTrack(MediaStreamTrack):
    """A WebRTC audio track fed by an :class:`AudioStream`."""

    kind = "audio"

    def __init__(
        self,
        stream: AudioStream,
        *,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        block_size: int = AUDIO_BLOCK_SIZE,
    ) -> None:
        super().__init__()
        self._stream = stream
        self._sample_rate = sample_rate
        self._block_size = block_size
        self._active = False
        self._timestamp = 0

    def set_active(self, active: bool) -> None:
        self._active = bool(active)

    @property
    def is_active(self) -> bool:
        return self._active

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        if self._active:
            data = self._stream.get_captured_frame()
            if data is None:
                await asyncio.sleep(0.02)
                data = self._stream.get_captured_frame()
            if data is None:
                data = np.zeros((1, self._block_size), dtype=np.int16)
            else:
                data = normalize_frame(data, self._block_size)
        else:
            await asyncio.sleep(0.05)
            data = np.zeros((1, self._block_size), dtype=np.int16)
        frame = av.AudioFrame.from_ndarray(data, format="s16", layout="mono")
        frame.sample_rate = self._sample_rate
        frame.pts = self._timestamp
        frame.time_base = fractions.Fraction(1, self._sample_rate)
        self._timestamp += self._block_size
        return frame


class CallManager:
    """Coordinates voice calls over an existing P2P WebRTC session.

    Emits the following events (subscribe with :meth:`on`):
    ``call_state_changed``, ``call_incoming``, ``call_ended`` and ``audio_level``.
    """

    def __init__(
        self,
        p2p_manager: Any,
        *,
        audio_stream: AudioStream | None = None,
        user_id: str | None = None,
        auth_manager: Any | None = None,
        current_user_id: str | None = None,
        ringing_timeout: float = 30.0,
        media_timeout: float = 10.0,
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
        self._audio = audio_stream if audio_stream is not None else AudioStream()
        self._user_id = user_id
        self._auth_manager = auth_manager or getattr(p2p_manager, "auth_manager", None)
        self._ringing_timeout = ringing_timeout
        self._media_timeout = media_timeout

        self._state = CALL_IDLE
        self._call_id: str | None = None
        self._peer_id: str | None = None
        self._track: AudioTrack | None = None
        self._muted = False
        self._pending_invite: dict[str, Any] | None = None
        self._remote_reader: asyncio.Task | None = None
        self._ringing_timer: asyncio.TimerHandle | None = None
        self._media_timer: asyncio.TimerHandle | None = None
        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._closed = False

        self._handlers = {
            "data_channel_message": self._on_channel_message,
            "peer_disconnected": self._on_peer_disconnected,
        }
        for event, handler in self._handlers.items():
            if hasattr(self._p2p, "on"):
                self._p2p.on(event, handler)

        self.p2p = p2p_manager
        self.user_id = user_id
        self.audio_stream = self._audio

    @property
    def state(self) -> str:
        return self._state

    @property
    def call_id(self) -> str | None:
        return self._call_id

    @property
    def peer_id(self) -> str | None:
        return self._peer_id

    @property
    def is_in_call(self) -> bool:
        return self._state not in (CALL_IDLE, CALL_ENDED)

    @property
    def is_muted(self) -> bool:
        return self._muted

    def on(self, event: str, callback: Listener) -> Listener:
        self._listeners[event].append(callback)
        return callback

    def off(self, event: str, callback: Listener) -> None:
        callbacks = self._listeners.get(event, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks:
            self._listeners.pop(event, None)

    # --- caller ------------------------------------------------------------

    async def start_call(self, friend_id: str) -> str:
        if self._state not in (CALL_IDLE, CALL_ENDED):
            raise CallError("A call is already in progress")
        friend_id = str(friend_id)
        if not self._p2p.is_connected(friend_id):
            await self._p2p.connect_to_peer(friend_id)
            if not await self._wait_open(friend_id):
                raise CallError(f"Could not reach {friend_id}")
        self._call_id = str(uuid.uuid4())
        self._peer_id = friend_id
        self._ensure_track(friend_id)
        self._start_remote_listener(friend_id)
        offer = await self._p2p.create_renegotiation_offer(friend_id)
        await self._send_json(
            friend_id,
            {
                "type": "call_invite",
                "call_id": self._call_id,
                "from": self._get_user_id(),
                "offer": offer,
            },
        )
        self._set_state(CALL_RINGING_OUT)
        self._arm_ringing_timer()
        return self._call_id

    async def accept_call(self, call_id: str, peer_id: str, offer: Any = None) -> bool:
        if self._state not in (CALL_IDLE, CALL_RINGING_IN, CALL_ENDED):
            await self._send_json(
                peer_id,
                {"type": "call_reject", "call_id": call_id, "reason": "busy"},
            )
            return False
        self._call_id = call_id
        self._peer_id = str(peer_id)
        self._ensure_track(self._peer_id)
        self._start_remote_listener(self._peer_id)
        answer = None
        if isinstance(offer, dict):
            answer = await self._p2p.create_renegotiation_answer(self._peer_id, offer)
        await self._send_json(
            self._peer_id,
            {
                "type": "call_answer",
                "call_id": call_id,
                "from": self._get_user_id(),
                "answer": answer,
            },
        )
        self._set_state(CALL_CONNECTING)
        self._arm_media_timer()
        return True

    async def reject_call(self, call_id: str, peer_id: str) -> None:
        await self._send_json(peer_id, {"type": "call_reject", "call_id": call_id})
        self._cleanup()
        self._set_state(CALL_ENDED)

    async def end_call(self) -> None:
        if self._state in (CALL_IDLE, CALL_ENDED):
            return
        peer_id = self._peer_id
        call_id = self._call_id
        if peer_id and call_id:
            await self._send_json(peer_id, {"type": "call_end", "call_id": call_id})
        self._cleanup()
        self._set_state(CALL_ENDED)
        await self._emit("call_ended", peer_id, "ended")

    def toggle_mute(self) -> bool:
        if not self.is_in_call:
            return self._muted
        self._muted = not self._muted
        if self._muted:
            self._audio.stop_capture()
        else:
            try:
                self._audio.start_capture()
            except AudioDeviceError:
                logger.warning("Could not restart audio capture", exc_info=True)
        return self._muted

    # --- incoming handlers -------------------------------------------------

    def _on_channel_message(self, peer_id: str, data: Any) -> None:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return
        if not isinstance(payload, dict) or payload.get("type") not in CALL_TYPES:
            return
        msg_type = payload["type"]
        if msg_type == "call_invite":
            asyncio.ensure_future(self._on_call_invite(str(peer_id), payload))
        elif msg_type == "call_answer":
            asyncio.ensure_future(self._on_call_answer(payload))
        elif msg_type == "call_reject":
            asyncio.ensure_future(self._on_call_reject(payload))
        elif msg_type == "call_end":
            asyncio.ensure_future(self._on_call_end(payload))

    async def _on_call_invite(self, peer_id: str, payload: dict[str, Any]) -> None:
        if self._state not in (CALL_IDLE, CALL_ENDED):
            await self._send_json(
                peer_id,
                {
                    "type": "call_reject",
                    "call_id": payload.get("call_id"),
                    "reason": "busy",
                },
            )
            return
        call_id = payload.get("call_id")
        offer = payload.get("offer")
        self._pending_invite = {
            "call_id": call_id,
            "peer_id": peer_id,
            "offer": offer,
        }
        self._set_state(CALL_RINGING_IN)
        await self._emit("call_incoming", call_id, peer_id, offer)

    async def _on_call_answer(self, payload: dict[str, Any]) -> None:
        call_id = payload.get("call_id")
        if call_id != self._call_id or self._state not in (
            CALL_RINGING_OUT,
            CALL_CONNECTING,
        ):
            return
        answer = payload.get("answer")
        if isinstance(answer, dict):
            await self._p2p.apply_remote_answer(self._peer_id, answer)
        self._cancel_ringing_timer()
        self._set_state(CALL_ACTIVE)
        self._arm_media_timer()

    async def _on_call_reject(self, payload: dict[str, Any]) -> None:
        if payload.get("call_id") != self._call_id:
            return
        self._cleanup()
        self._set_state(CALL_ENDED)
        await self._emit("call_ended", self._peer_id, "rejected")

    async def _on_call_end(self, payload: dict[str, Any]) -> None:
        if payload.get("call_id") != self._call_id:
            return
        self._cleanup()
        self._set_state(CALL_ENDED)
        await self._emit("call_ended", self._peer_id, "ended")

    def _on_peer_disconnected(self, peer_id: str) -> None:
        if str(peer_id) != self._peer_id or not self.is_in_call:
            return
        asyncio.ensure_future(self._handle_peer_disconnected())

    async def _handle_peer_disconnected(self) -> None:
        self._cleanup()
        self._set_state(CALL_ENDED)
        await self._emit("call_ended", self._peer_id, "connection_lost")

    # --- internals ---------------------------------------------------------

    def _ensure_track(self, peer_id: str) -> None:
        if self._track is None:
            self._track = AudioTrack(self._audio)
        self._track.set_active(True)
        if not self._p2p.has_audio_sender(peer_id):
            self._p2p.add_audio_track(peer_id, self._track)

    def _start_remote_listener(self, peer_id: str) -> None:
        self._stop_remote_reader()
        self._p2p.on_remote_track(peer_id, self._on_remote_track)

    def _on_remote_track(self, track: Any) -> None:
        if self._remote_reader is not None and not self._remote_reader.done():
            return
        self._remote_reader = asyncio.ensure_future(self._read_remote_audio(track))

    async def _read_remote_audio(self, track: Any) -> None:
        first_frame = False
        while not self._closed and self._state not in (CALL_IDLE, CALL_ENDED):
            if self._state not in (CALL_CONNECTING, CALL_ACTIVE):
                await asyncio.sleep(0.05)
                continue
            try:
                frame = await asyncio.wait_for(track.recv(), timeout=1.0)
            except TimeoutError:
                continue
            except Exception:
                break
            try:
                data = frame.to_ndarray()
            except Exception:
                continue
            if self._state == CALL_CONNECTING and not first_frame:
                first_frame = True
                self._cancel_media_timer()
                self._set_state(CALL_ACTIVE)
            data = normalize_frame(data, self._audio.block_size)
            self._audio.play_frame(data)
            await self._emit("audio_level", frame_energy(data))

    def _arm_ringing_timer(self) -> None:
        self._cancel_ringing_timer()
        loop = asyncio.get_running_loop()

        def _on_timeout() -> None:
            logger.info("Call ringing timed out")
            asyncio.ensure_future(self.end_call())

        self._ringing_timer = loop.call_later(self._ringing_timeout, _on_timeout)

    def _cancel_ringing_timer(self) -> None:
        if self._ringing_timer is not None:
            self._ringing_timer.cancel()
            self._ringing_timer = None

    def _arm_media_timer(self) -> None:
        self._cancel_media_timer()
        loop = asyncio.get_running_loop()

        def _on_timeout() -> None:
            logger.warning("No media received within %.0fs", self._media_timeout)
            asyncio.ensure_future(self.end_call())

        self._media_timer = loop.call_later(self._media_timeout, _on_timeout)

    def _cancel_media_timer(self) -> None:
        if self._media_timer is not None:
            self._media_timer.cancel()
            self._media_timer = None

    def _stop_remote_reader(self) -> None:
        if self._remote_reader is not None:
            self._remote_reader.cancel()
            self._remote_reader = None

    def _cleanup(self) -> None:
        self._cancel_ringing_timer()
        self._cancel_media_timer()
        self._stop_remote_reader()
        if self._track is not None:
            self._track.set_active(False)
        self._audio.stop_capture()
        self._audio.stop_playback()
        self._pending_invite = None
        self._call_id = None
        self._peer_id = None
        self._muted = False

    def _set_state(self, state: str) -> None:
        if state not in CALL_STATES:
            raise ValueError(f"Invalid call state: {state}")
        old = self._state
        self._state = state
        if state == CALL_ACTIVE and old != CALL_ACTIVE:
            self._start_audio_devices()
        if state != old:
            asyncio.ensure_future(self._emit("call_state_changed", state, self._peer_id))

    def _start_audio_devices(self) -> None:
        try:
            self._audio.start_capture()
        except AudioDeviceError:
            logger.warning("Could not start audio capture", exc_info=True)
        try:
            self._audio.start_playback()
        except AudioDeviceError:
            logger.warning("Could not start audio playback", exc_info=True)

    async def _send_json(self, peer_id: str, payload: dict[str, Any]) -> None:
        channel = self._p2p.get_data_channel(peer_id)
        if channel is None:
            return
        try:
            channel.send(json.dumps(payload))
        except Exception:
            logger.warning("Failed to send call payload to %s", peer_id, exc_info=True)

    async def _wait_open(self, friend_id: str, timeout: float = 15.0) -> bool:
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

    def _get_user_id(self) -> str:
        if self._user_id:
            return str(self._user_id)
        if self._auth_manager is not None:
            current = self._auth_manager.get_current_user()
            if current is not None and getattr(current, "id", None):
                self._user_id = str(current.id)
                self.user_id = self._user_id
                return self._user_id
        p2p_user_id = getattr(self._p2p, "user_id", None)
        if p2p_user_id:
            self._user_id = str(p2p_user_id)
            self.user_id = self._user_id
            return self._user_id
        user = UserRepository().get_current()
        if user is not None and getattr(user, "id", None):
            self._user_id = str(user.id)
            self.user_id = self._user_id
            return self._user_id
        raise RuntimeError("No local user is available")

    async def _emit(self, event: str, *args: Any) -> None:
        for callback in list(self._listeners.get(event, [])):
            try:
                result = self._call_listener(callback, *args)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Call event listener failed: %s", event)

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
        for event, handler in self._handlers.items():
            if hasattr(self._p2p, "off"):
                self._p2p.off(event, handler)
        self._cleanup()
        self._audio.close()
        self._listeners.clear()


__all__ = [
    "AudioDeviceError",
    "AudioStream",
    "AudioTrack",
    "CallError",
    "CallManager",
    "frame_energy",
    "is_speech",
    "normalize_frame",
    "CALL_ACTIVE",
    "CALL_CONNECTING",
    "CALL_ENDED",
    "CALL_IDLE",
    "CALL_RINGING_IN",
    "CALL_RINGING_OUT",
    "CALL_STATES",
    "CALL_TYPES",
]
