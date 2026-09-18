from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from typing import Any

import pytest

from client.network.p2p_manager import P2PManager
from client.network.webrtc_session import WebRTCSession, _parse_ice_candidate

SIGNALING_EVENT_BY_TYPE = {
    "offer": "signaling_offer",
    "answer": "signaling_answer",
    "ice_candidate": "signaling_ice",
}


class FakeSignaling:
    """In-memory signaling relay that routes signaling between two peers."""

    def __init__(self, peer_id: str) -> None:
        self.peer_id = peer_id
        self.peers: dict[str, FakeSignaling] = {}
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self._listeners: dict[str, list[Any]] = defaultdict(list)

    def on(self, event: str, callback: Any) -> Any:
        self._listeners[event].append(callback)
        return callback

    def off(self, event: str, callback: Any) -> None:
        callbacks = self._listeners.get(event, [])
        if callback in callbacks:
            callbacks.remove(callback)

    async def send(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        if type_ != "signaling" or not isinstance(payload, dict):
            return
        self.sent.append((type_, payload))
        target = self.peers.get(payload.get("to"))
        if target is None:
            return
        event = SIGNALING_EVENT_BY_TYPE[payload["type"]]
        await target._deliver(event, {"from": self.peer_id, "data": payload["data"]})

    async def _deliver(self, event: str, payload: dict[str, Any]) -> None:
        for callback in list(self._listeners.get(event, [])):
            result = callback(payload)
            if inspect.isawaitable(result):
                await result


async def test_webrtc_session_offer_serialization() -> None:
    session = WebRTCSession(ice_servers=[])
    offer = await session.create_offer()
    assert offer["type"] == "offer"
    assert "sdp" in offer and offer["sdp"]
    await session.close()
    assert session.is_closed


def test_parse_ice_candidate() -> None:
    candidate = _parse_ice_candidate(
        "candidate:125a101b 1 udp 2130706431 192.168.0.4 49848 typ host", "0", 0
    )
    assert candidate.ip == "192.168.0.4"
    assert candidate.port == 49848
    assert candidate.component == 1
    assert candidate.protocol == "udp"
    assert candidate.type == "host"
    assert candidate.sdpMid == "0"
    assert candidate.sdpMLineIndex == 0


async def test_p2p_connection_and_message() -> None:
    sig_a = FakeSignaling("A")
    sig_b = FakeSignaling("B")
    sig_a.peers["B"] = sig_b
    sig_b.peers["A"] = sig_a

    mgr_a = P2PManager(sig_a, ice_servers=[], current_user_id="A")
    mgr_b = P2PManager(sig_b, ice_servers=[], current_user_id="B")

    opened = asyncio.Event()
    mgr_a.on("data_channel_open", lambda peer: opened.set())
    received = asyncio.Event()
    messages: list[Any] = []

    def on_message(peer: str, data: Any) -> None:
        messages.append(data)
        received.set()

    mgr_b.on("data_channel_message", on_message)

    try:
        await mgr_a.connect_to_peer("B")
        await asyncio.wait_for(opened.wait(), timeout=20)

        assert mgr_a.get_data_channel("B") is not None
        assert mgr_b.get_data_channel("A") is not None
        assert mgr_a.is_connected("B")
        assert mgr_b.is_connected("A")

        await mgr_a.send_message("B", "hello p2p")
        await asyncio.wait_for(received.wait(), timeout=10)
        assert messages == ["hello p2p"]

        disconnected = asyncio.Event()
        mgr_b.on("peer_disconnected", lambda peer: disconnected.set())
        mgr_a.disconnect_peer("B")
        await asyncio.wait_for(disconnected.wait(), timeout=10)
    finally:
        mgr_a.close()
        mgr_b.close()
        await asyncio.sleep(0.1)


async def test_connection_timeout_emits_failed() -> None:
    sig = FakeSignaling("A")
    mgr = P2PManager(
        sig,
        ice_servers=[],
        current_user_id="A",
        max_retries=1,
        connection_timeout=0.3,
        backoff=0.0,
    )
    failed = asyncio.Event()
    mgr.on("connection_failed", lambda peer, err: failed.set())
    try:
        await mgr.connect_to_peer("B")
        await asyncio.wait_for(failed.wait(), timeout=10)
    finally:
        mgr.close()
        await asyncio.sleep(0.1)


async def test_p2p_retries_then_emits_failed() -> None:
    sig = FakeSignaling("A")
    mgr = P2PManager(
        sig,
        ice_servers=[],
        current_user_id="A",
        max_retries=2,
        connection_timeout=0.2,
        backoff=0.0,
    )
    failed = asyncio.Event()
    mgr.on("connection_failed", lambda peer, err: failed.set())
    try:
        await mgr.connect_to_peer("B")
        await asyncio.wait_for(failed.wait(), timeout=10)
        assert mgr.get_data_channel("B") is None
    finally:
        mgr.close()
        await asyncio.sleep(0.1)


@pytest.mark.parametrize(
    "sdp",
    [
        "candidate:842163049 1 udp 1677729535 192.168.0.4 45651 typ host generation 0",
        "candidate:842163049 1 udp 1677729535 2001:db8::1 45651 typ host raddr 0.0.0.0 rport 0",
    ],
)
def test_parse_ice_candidate_variants(sdp: str) -> None:
    candidate = _parse_ice_candidate(sdp, "0", 0)
    assert candidate.type == "host"
    assert candidate.component == 1
