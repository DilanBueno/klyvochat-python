from __future__ import annotations

import asyncio
import collections
from typing import Any

import numpy as np

from client.core.voice import (
    AudioStream,
    AudioTrack,
    CallManager,
    frame_energy,
    is_speech,
    normalize_frame,
)
from tests.test_p2p import FakeSignaling


class FakeAudioStream(AudioStream):
    """AudioStream without real devices; buffers capture and playback."""

    def __init__(self, block_size: int = 960) -> None:
        self._capture_started = False
        self._block_size = block_size
        self._sample_rate = 48000
        self.captured: collections.deque[np.ndarray] = collections.deque()
        self.played: collections.deque[np.ndarray] = collections.deque()

    def start_capture(self, device_id=None) -> None:
        self._capture_started = True
        for _ in range(200):
            self.captured.append(np.zeros((1, self.block_size), dtype=np.int16))

    def stop_capture(self) -> None:
        self._capture_started = False
        self.captured.clear()

    def start_playback(self, device_id=None) -> None:
        pass

    def stop_playback(self) -> None:
        pass

    def play_frame(self, frame: np.ndarray) -> None:
        self.played.append(normalize_frame(frame, self.block_size))

    def get_captured_frame(self) -> np.ndarray | None:
        return self.captured.popleft() if self.captured else None

    def get_energy(self) -> float:
        return 0.0

    def close(self) -> None:
        self.stop_capture()
        self.stop_playback()


def make_pair() -> tuple[CallManager, CallManager, FakeAudioStream, FakeAudioStream]:
    sig_a = FakeSignaling("A")
    sig_b = FakeSignaling("B")
    sig_a.peers["B"] = sig_b
    sig_b.peers["A"] = sig_a
    p2p_a = _make_p2p("A", sig_a)
    p2p_b = _make_p2p("B", sig_b)
    audio_a = FakeAudioStream()
    audio_b = FakeAudioStream()
    calls_a = CallManager(p2p_a, audio_stream=audio_a, current_user_id="A")
    calls_b = CallManager(p2p_b, audio_stream=audio_b, current_user_id="B")
    return calls_a, calls_b, audio_a, audio_b


def _make_p2p(user_id: str, signaling: FakeSignaling):
    from client.network.p2p_manager import P2PManager

    return P2PManager(signaling, ice_servers=[], current_user_id=user_id)


async def wait_state(calls: CallManager, state: str, timeout: float = 20) -> None:
    if calls.state == state:
        return
    changed = asyncio.Event()

    def on_state(new_state: str, peer_id: str | None) -> None:
        if new_state == state:
            changed.set()

    calls.on("call_state_changed", on_state)
    try:
        await asyncio.wait_for(changed.wait(), timeout=timeout)
    finally:
        calls.off("call_state_changed", on_state)


def test_frame_helpers() -> None:
    silence = np.zeros((1, 960), dtype=np.int16)
    assert frame_energy(silence) == 0.0
    assert not is_speech(silence)

    tone = (np.sin(np.linspace(0, 10, 960)) * 10000).astype(np.int16).reshape(1, -1)
    assert frame_energy(tone) > 0.05
    assert is_speech(tone)

    flat = normalize_frame(np.zeros(960, dtype=np.int16))
    assert flat.shape == (1, 960)
    assert flat.dtype == np.int16

    two_d = normalize_frame(np.zeros((960, 1), dtype=np.int16))
    assert two_d.shape == (1, 960)

    short = normalize_frame(np.zeros((480, 1), dtype=np.int16))
    assert short.shape == (1, 960)

    float_frame = normalize_frame(np.zeros((1, 960), dtype=np.float32))
    assert float_frame.dtype == np.int16


async def test_audio_track_recv() -> None:
    stream = FakeAudioStream()
    stream.start_capture()
    track = AudioTrack(stream)
    track.set_active(True)
    frame = await track.recv()
    assert frame.sample_rate == 48000
    assert frame.samples == 960
    data = frame.to_ndarray()
    assert data.size == 960
    assert data.dtype == np.int16


async def test_call_flow_reaches_active_and_audio_flows() -> None:
    calls_a, calls_b, audio_a, audio_b = make_pair()
    incoming = asyncio.Event()
    invite: dict[str, Any] = {}

    def on_incoming(call_id: str, peer_id: str, offer: Any) -> None:
        invite["call_id"] = call_id
        invite["peer_id"] = peer_id
        invite["offer"] = offer
        incoming.set()

    calls_b.on("call_incoming", on_incoming)
    try:
        call_id = await calls_a.start_call("B")
        await asyncio.wait_for(incoming.wait(), timeout=20)
        assert invite["call_id"] == call_id
        assert invite["peer_id"] == "A"
        assert isinstance(invite["offer"], dict)

        await calls_b.accept_call(invite["call_id"], invite["peer_id"], invite["offer"])

        await wait_state(calls_a, "active")
        await wait_state(calls_b, "active")

        assert calls_a.state == "active"
        assert calls_b.state == "active"
        assert calls_a.is_in_call
        assert calls_b.is_in_call

        await asyncio.sleep(1.5)
        assert len(audio_b.played) > 0, "remote audio should reach B"
        assert len(audio_a.played) > 0, "remote audio should reach A"

        ended_a = asyncio.Event()
        calls_a.on("call_ended", lambda peer, reason: ended_a.set())
        await calls_b.end_call()
        await asyncio.wait_for(ended_a.wait(), timeout=5)
        assert calls_a.state == "ended"
        assert calls_b.state == "ended"
        assert not calls_a.is_in_call
    finally:
        calls_a.close()
        calls_b.close()
        await asyncio.sleep(0.1)


async def test_call_rejected() -> None:
    calls_a, calls_b, _, _ = make_pair()
    incoming = asyncio.Event()
    invite: dict[str, Any] = {}

    def on_incoming(call_id: str, peer_id: str, offer: Any) -> None:
        invite.update(call_id=call_id, peer_id=peer_id, offer=offer)
        incoming.set()

    calls_b.on("call_incoming", on_incoming)
    rejected = asyncio.Event()
    calls_a.on("call_ended", lambda peer, reason: rejected.set() if reason == "rejected" else None)
    try:
        await calls_a.start_call("B")
        await asyncio.wait_for(incoming.wait(), timeout=20)
        await calls_b.reject_call(invite["call_id"], invite["peer_id"])
        await asyncio.wait_for(rejected.wait(), timeout=5)
        assert calls_a.state == "ended"
        assert calls_b.state == "ended"
        assert not calls_a.is_in_call
    finally:
        calls_a.close()
        calls_b.close()
        await asyncio.sleep(0.1)


async def test_call_ends_on_peer_disconnect() -> None:
    calls_a, calls_b, _, _ = make_pair()
    ended = asyncio.Event()
    calls_a.on("call_ended", lambda peer, reason: ended.set())
    try:
        await calls_a.start_call("B")
        await asyncio.sleep(0.2)
        # Simulate the P2P channel closing on B's side.
        calls_a._on_peer_disconnected("B")
        await asyncio.wait_for(ended.wait(), timeout=5)
        assert calls_a.state == "ended"
    finally:
        calls_a.close()
        calls_b.close()
        await asyncio.sleep(0.1)


def test_list_devices() -> None:
    stream = AudioStream()
    devices = stream.list_devices()
    assert isinstance(devices, list)
    for device in devices:
        assert {"id", "name", "inputs", "outputs", "default"} <= set(device)
    stream.close()
