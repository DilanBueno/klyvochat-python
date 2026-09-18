from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine

import client.core.messaging as messaging_module
from client.core.messaging import MessageManager
from client.network.p2p_manager import P2PManager
from client.storage.database import Base
from client.storage.models import Message
from client.storage.repositories import MessageRepository
from tests.test_p2p import FakeSignaling


def make_repository() -> MessageRepository:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = _sessionmaker(engine)

    @contextmanager
    def _session() -> Iterator[Any]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return MessageRepository(session_factory=_session)


def _sessionmaker(engine: Any) -> Any:
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, expire_on_commit=False)


def make_p2p_pair() -> tuple[P2PManager, P2PManager, FakeSignaling, FakeSignaling]:
    sig_a = FakeSignaling("A")
    sig_b = FakeSignaling("B")
    sig_a.peers["B"] = sig_b
    sig_b.peers["A"] = sig_a
    mgr_a = P2PManager(sig_a, ice_servers=[], current_user_id="A")
    mgr_b = P2PManager(sig_b, ice_servers=[], current_user_id="B")
    return mgr_a, mgr_b, sig_a, sig_b


async def wait_connected(mgr: P2PManager, peer_id: str, timeout: float = 20) -> None:
    if mgr.is_connected(peer_id):
        return
    opened = asyncio.Event()

    def _on_open(peer: str) -> None:
        if str(peer) == peer_id:
            opened.set()

    mgr.on("data_channel_open", _on_open)
    try:
        await asyncio.wait_for(opened.wait(), timeout=timeout)
    finally:
        mgr.off("data_channel_open", _on_open)


async def test_send_receive_and_delivery_ack() -> None:
    p2p_a, p2p_b, _, _ = make_p2p_pair()
    repo_a = make_repository()
    repo_b = make_repository()
    msgs_a = MessageManager(p2p_a, message_repo=repo_a, current_user_id="A")
    msgs_b = MessageManager(p2p_b, message_repo=repo_b, current_user_id="B")

    received = asyncio.Event()
    received_data: list[Any] = []

    def on_received(message: Any) -> None:
        received_data.append(message)
        received.set()

    msgs_b.on("message_received", on_received)
    try:
        sent = await msgs_a.send_message("B", "olá, mundo")
        assert sent is not None
        assert sent.sender_id == "A"
        assert sent.receiver_id == "B"

        await asyncio.wait_for(received.wait(), timeout=10)
        assert received_data and received_data[0].content == "olá, mundo"
        assert received_data[0].sender_id == "A"

        assert repo_a.get_conversation("A", "B")[0].content == "olá, mundo"

        delivered = asyncio.Event()
        msgs_a.on("message_delivered", lambda msg_id: delivered.set())
        await asyncio.wait_for(delivered.wait(), timeout=5)
        assert repo_a.get_by_msg_id(sent.msg_id).delivered is True

        assert repo_b.get_conversation("B", "A")[0].content == "olá, mundo"
        assert repo_b.get_conversation("B", "A")[0].delivered is True
    finally:
        msgs_a.close()
        msgs_b.close()
        p2p_a.close()
        p2p_b.close()
        await asyncio.sleep(0.1)


async def test_typing_indicators() -> None:
    old_delay = messaging_module.TYPING_STOP_DELAY
    messaging_module.TYPING_STOP_DELAY = 0.2
    p2p_a, p2p_b, _, _ = make_p2p_pair()
    repo_a = make_repository()
    repo_b = make_repository()
    msgs_a = MessageManager(p2p_a, message_repo=repo_a, current_user_id="A", wait_timeout=5)
    msgs_b = MessageManager(p2p_b, message_repo=repo_b, current_user_id="B", wait_timeout=5)

    states: list[tuple[str, bool]] = []
    typing_seen = asyncio.Event()

    def on_typing(friend_id: str, is_typing: bool) -> None:
        states.append((friend_id, is_typing))
        if is_typing:
            typing_seen.set()

    msgs_b.on("typing", on_typing)
    try:
        await p2p_a.connect_to_peer("B")
        await wait_connected(p2p_a, "B")
        await msgs_a.notify_typing("B")
        await asyncio.wait_for(typing_seen.wait(), timeout=5)
        assert ("A", True) in states

        await asyncio.sleep(0.6)
        assert ("A", False) in states
        assert not msgs_a._typing_active
    finally:
        msgs_a.close()
        msgs_b.close()
        p2p_a.close()
        p2p_b.close()
        messaging_module.TYPING_STOP_DELAY = old_delay
        await asyncio.sleep(0.1)


async def test_read_receipts() -> None:
    p2p_a, p2p_b, _, _ = make_p2p_pair()
    repo_a = make_repository()
    repo_b = make_repository()
    msgs_a = MessageManager(p2p_a, message_repo=repo_a, current_user_id="A", wait_timeout=5)
    msgs_b = MessageManager(p2p_b, message_repo=repo_b, current_user_id="B", wait_timeout=5)

    received = asyncio.Event()
    msgs_b.on("message_received", lambda message: received.set())
    read_seen = asyncio.Event()
    msgs_a.on("message_read", lambda friend_id: read_seen.set())

    try:
        sent = await msgs_a.send_message("B", "você leu?")
        assert sent is not None
        await asyncio.wait_for(received.wait(), timeout=10)

        assert repo_a.get_by_msg_id(sent.msg_id).read is False
        await msgs_b.mark_conversation_read("A")
        await asyncio.wait_for(read_seen.wait(), timeout=5)
        assert repo_a.get_by_msg_id(sent.msg_id).read is True
    finally:
        msgs_a.close()
        msgs_b.close()
        p2p_a.close()
        p2p_b.close()
        await asyncio.sleep(0.1)


async def test_resend_pending_undelivered() -> None:
    p2p_a, p2p_b, _, _ = make_p2p_pair()
    repo_a = make_repository()
    repo_b = make_repository()
    msgs_a = MessageManager(p2p_a, message_repo=repo_a, current_user_id="A", wait_timeout=5)
    msgs_b = MessageManager(p2p_b, message_repo=repo_b, current_user_id="B", wait_timeout=5)

    received = asyncio.Event()
    got: list[Any] = []

    def on_received(message: Any) -> None:
        got.append(message)
        received.set()

    msgs_b.on("message_received", on_received)
    try:
        await p2p_a.connect_to_peer("B")
        await wait_connected(p2p_a, "B")

        ts = datetime.now(UTC).replace(tzinfo=None)
        repo_a.save_message(
            Message(
                msg_id="pending-1",
                sender_id="A",
                receiver_id="B",
                content="mensagem pendente",
                timestamp=ts,
                read=False,
                delivered=False,
            )
        )
        await msgs_a._resend_pending("B")
        await asyncio.wait_for(received.wait(), timeout=5)
        assert got and got[0].content == "mensagem pendente"
        assert got[0].msg_id == "pending-1"
    finally:
        msgs_a.close()
        msgs_b.close()
        p2p_a.close()
        p2p_b.close()
        await asyncio.sleep(0.1)


async def test_send_to_offline_peer_returns_none() -> None:
    sig_a = FakeSignaling("A")
    p2p_a = P2PManager(
        sig_a,
        ice_servers=[],
        current_user_id="A",
        max_retries=1,
        connection_timeout=0.2,
        backoff=0.0,
    )
    msgs_a = MessageManager(p2p_a, current_user_id="A", wait_timeout=1)
    try:
        result = await msgs_a.send_message("B", "ninguém vai receber")
        assert result is None
    finally:
        msgs_a.close()
        p2p_a.close()
        await asyncio.sleep(0.1)


def test_repository_helpers() -> None:
    repo = make_repository()
    now = datetime.now(UTC).replace(tzinfo=None)
    base = now - timedelta(minutes=5)
    repo.save_message(
        Message(msg_id="m1", sender_id="friend", receiver_id="me", content="oi", timestamp=base)
    )
    repo.save_message(
        Message(
            msg_id="m2",
            sender_id="friend",
            receiver_id="me",
            content="visto?",
            timestamp=base + timedelta(minutes=1),
            read=True,
        )
    )
    repo.save_message(
        Message(
            msg_id="m3",
            sender_id="me",
            receiver_id="friend",
            content="envio",
            timestamp=base + timedelta(minutes=2),
            delivered=False,
        )
    )
    assert repo.get_unread_count("me", "friend") == 1
    assert [m.msg_id for m in repo.get_unread_from_friend("me", "friend")] == ["m1"]
    assert [m.msg_id for m in repo.get_undelivered("me")] == ["m3"]
    assert [m.msg_id for m in repo.get_conversation("me", "friend")] == ["m1", "m2", "m3"]

    repo.mark_delivered("m3")
    assert repo.get_by_msg_id("m3").delivered is True
    assert repo.get_undelivered("me") == []

    repo.mark_read_by_msg_ids(["m1"])
    assert repo.get_unread_count("me", "friend") == 0

    old = repo.delete_older_than(now - timedelta(days=1))
    assert old == 0
    new_cutoff = repo.delete_older_than(now + timedelta(seconds=1))
    assert new_cutoff == 3
    assert repo.get_conversation("me", "friend") == []
