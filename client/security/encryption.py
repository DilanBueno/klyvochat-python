from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

NONCE_SIZE = 12
DERIVE_INFO = b"klyvochat-message-key-v1"


class MessageEncryptionError(Exception):
    """Raised when message encryption/decryption fails."""


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


class MessageEncryption:
    """End-to-end encryption for chat messages (X25519 ECDH + HKDF + AES-GCM)."""

    def derive_shared_secret(self, my_private_key: bytes, peer_public_key: bytes) -> bytes:
        private_key = X25519PrivateKey.from_private_bytes(my_private_key)
        public_key = X25519PublicKey.from_public_bytes(peer_public_key)
        return private_key.exchange(public_key)

    def derive_key(self, shared_secret: bytes) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=DERIVE_INFO,
        )
        return hkdf.derive(shared_secret)

    def encrypt(self, plaintext: bytes, key: bytes) -> dict[str, str]:
        nonce = os.urandom(NONCE_SIZE)
        encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        return {
            "ciphertext": _b64encode(ciphertext),
            "nonce": _b64encode(nonce),
            "tag": _b64encode(encryptor.tag),
        }

    def decrypt(self, encrypted: dict[str, Any], key: bytes) -> bytes:
        try:
            ciphertext = _b64decode(encrypted["ciphertext"])
            nonce = _b64decode(encrypted["nonce"])
            tag = _b64decode(encrypted["tag"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MessageEncryptionError("Invalid encrypted payload") from exc
        try:
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            return decryptor.update(ciphertext) + decryptor.finalize()
        except Exception as exc:
            raise MessageEncryptionError("Failed to decrypt message") from exc

    def encrypt_message(
        self,
        message: str,
        peer_public_key: bytes,
        my_private_key: bytes,
    ) -> dict[str, str]:
        """Encrypt ``message`` for a peer using ECDH-derived session key."""
        shared_secret = self.derive_shared_secret(my_private_key, peer_public_key)
        key = self.derive_key(shared_secret)
        return self.encrypt(message.encode("utf-8"), key)

    def decrypt_message(
        self,
        encrypted: dict[str, Any],
        my_private_key: bytes,
        peer_public_key: bytes,
    ) -> str:
        """Decrypt a message received from a peer using the shared session key."""
        shared_secret = self.derive_shared_secret(my_private_key, peer_public_key)
        key = self.derive_key(shared_secret)
        plaintext = self.decrypt(encrypted, key)
        return plaintext.decode("utf-8")


__all__ = ["MessageEncryption", "MessageEncryptionError"]
