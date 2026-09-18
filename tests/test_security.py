from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from client.core.messaging import MessageManager
from client.network.p2p_manager import P2PManager
from client.security.encryption import MessageEncryption, MessageEncryptionError
from client.security.identity import UserIdentity
from client.security.keys import KeyManager, KeyManagerError
from client.storage.database import Base
from client.storage.repositories import KeyPairRepository, MessageRepository
from tests.test_p2p import FakeSignaling


def make_session_factory() -> Any:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _session() -> Iterator[Any]:
        session = session_maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _session


def make_key_repo() -> KeyPairRepository:
    return KeyPairRepository(session_factory=make_session_factory())


def make_message_repo() -> MessageRepository:
    return MessageRepository(session_factory=make_session_factory())


def _xkeypair() -> tuple[bytes, bytes]:
    private_key = X25519PrivateKey.generate()
    return private_key.public_key().public_bytes_raw(), private_key.private_bytes_raw()


async def test_key_manager_roundtrip() -> None:
    repo = make_key_repo()
    km = KeyManager("user-1", key_repo=repo)
    assert not km.has_keys()

    public_key = km.ensure_keys("correct horse battery")
    assert public_key == km.get_public_key()
    private_key = km.get_private_key()
    assert private_key and len(private_key) == 32

    km2 = KeyManager("user-1", key_repo=repo)
    assert km2.has_keys()
    assert km2.get_public_key() == public_key
    assert km2.get_private_key() is None
    assert not km2.unlock("wrong password")
    assert km2.unlock("correct horse battery")
    assert km2.get_private_key() == private_key

    exported = km2.export_public_key()
    assert KeyManager.import_peer_public_key(exported) == public_key
    with pytest.raises(KeyManagerError):
        KeyManager.import_peer_public_key("not-base64-!!!")
    with pytest.raises(KeyManagerError):
        KeyManager.import_peer_public_key(exported[:-2] + "AA")

    km2.lock()
    assert not km2.is_unlocked


def test_message_encryption_roundtrip() -> None:
    encryption = MessageEncryption()
    a_public, a_private = _xkeypair()
    b_public, b_private = _xkeypair()
    secret = "mensagem super secreta"

    ciphertext = encryption.encrypt_message(secret, b_public, a_private)
    assert isinstance(ciphertext, dict)
    assert {"ciphertext", "nonce", "tag"} <= set(ciphertext)
    assert secret not in str(ciphertext)

    plaintext = encryption.decrypt_message(ciphertext, b_private, a_public)
    assert plaintext == secret

    c_public, c_private = _xkeypair()
    with pytest.raises(MessageEncryptionError):
        encryption.decrypt_message(ciphertext, c_private, a_public)

    tampered = dict(ciphertext)
    tampered["nonce"] = tampered["nonce"][:-2] + "00"
    with pytest.raises(MessageEncryptionError):
        encryption.decrypt_message(tampered, b_private, a_public)


def test_identity_signatures_and_fingerprints() -> None:
    identity = UserIdentity()
    public_key, private_key = identity.generate_identity()
    data = b"klyvochat fingerprint verification"

    signature = identity.sign(data, private_key)
    assert identity.verify_signature(data, signature, public_key)
    assert not identity.verify_signature(b"tampered", signature, public_key)
    assert not identity.verify_signature(data, b"\x00" * len(signature), public_key)

    fingerprint = identity.get_fingerprint(public_key)
    groups = fingerprint.split()
    assert len(groups) == 8
    assert all(len(group) == 4 for group in groups)
    assert all(all(c in "0123456789ABCDEF" for c in group) for group in groups)
    assert identity.verify_fingerprint(fingerprint, public_key)
    tampered = "".join(fingerprint.split())
    flipped = ("0" if tampered[0] != "0" else "1") + tampered[1:]
    assert not identity.verify_fingerprint(flipped, public_key)


def _make_p2p_pair() -> tuple[P2PManager, P2PManager]:
    sig_a = FakeSignaling("A")
    sig_b = FakeSignaling("B")
    sig_a.peers["B"] = sig_b
    sig_b.peers["A"] = sig_a
    return (
        P2PManager(sig_a, ice_servers=[], current_user_id="A"),
        P2PManager(sig_b, ice_servers=[], current_user_id="B"),
    )


async def test_e2e_messages_over_p2p() -> None:
    p2p_a, p2p_b = _make_p2p_pair()
    keys_a = KeyManager("A", key_repo=make_key_repo())
    keys_b = KeyManager("B", key_repo=make_key_repo())
    keys_a.ensure_keys("senhaA")
    keys_b.ensure_keys("senhaB")
    encryption = MessageEncryption()

    msgs_a = MessageManager(
        p2p_a,
        message_repo=make_message_repo(),
        current_user_id="A",
        key_manager=keys_a,
        encryption=encryption,
    )
    msgs_b = MessageManager(
        p2p_b,
        message_repo=make_message_repo(),
        current_user_id="B",
        key_manager=keys_b,
        encryption=encryption,
    )

    received = asyncio.Event()
    got: list[Any] = []

    def on_received(message: Any) -> None:
        got.append(message)
        received.set()

    msgs_b.on("message_received", on_received)
    try:
        sent = await msgs_a.send_message("B", "segredo e2e")
        assert sent is not None
        assert sent.encrypted is True

        await asyncio.wait_for(received.wait(), timeout=15)
        assert got and got[0].content == "segredo e2e"
        assert got[0].encrypted is True

        assert msgs_b.get_peer_fingerprint("A") is not None
        fingerprint = msgs_b.get_peer_fingerprint("A")
        assert fingerprint and len(fingerprint.split()) == 8
    finally:
        msgs_a.close()
        msgs_b.close()
        p2p_a.close()
        p2p_b.close()
        keys_a.lock()
        keys_b.lock()
        await asyncio.sleep(0.1)


async def test_plaintext_fallback_without_keys() -> None:
    p2p_a, p2p_b = _make_p2p_pair()
    msgs_a = MessageManager(p2p_a, message_repo=make_message_repo(), current_user_id="A")
    msgs_b = MessageManager(p2p_b, message_repo=make_message_repo(), current_user_id="B")
    received = asyncio.Event()
    got: list[Any] = []

    def on_received(message: Any) -> None:
        got.append(message)
        received.set()

    msgs_b.on("message_received", on_received)
    try:
        sent = await msgs_a.send_message("B", "sem criptografia")
        assert sent is not None and sent.encrypted is False
        await asyncio.wait_for(received.wait(), timeout=15)
        assert got and got[0].content == "sem criptografia"
        assert got[0].encrypted is False
    finally:
        msgs_a.close()
        msgs_b.close()
        p2p_a.close()
        p2p_b.close()
        await asyncio.sleep(0.1)
