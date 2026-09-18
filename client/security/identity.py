from __future__ import annotations

import base64
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


class IdentityError(Exception):
    """Raised when an identity operation fails."""


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _public_key_from_bytes(public_key: bytes) -> Ed25519PublicKey:
    try:
        return Ed25519PublicKey.from_public_bytes(public_key)
    except Exception as exc:
        raise IdentityError("Invalid Ed25519 public key") from exc


class UserIdentity:
    """Ed25519 signatures and key fingerprints for identity verification."""

    def generate_identity(self) -> tuple[bytes, bytes]:
        """Generate a fresh Ed25519 identity, returning ``(public, private)``."""
        private_key = Ed25519PrivateKey.generate()
        return private_key.public_key().public_bytes_raw(), private_key.private_bytes_raw()

    def sign(self, data: bytes, private_key: bytes) -> bytes:
        private = Ed25519PrivateKey.from_private_bytes(private_key)
        return private.sign(data)

    def verify_signature(self, data: bytes, signature: bytes, public_key: bytes) -> bool:
        public = _public_key_from_bytes(public_key)
        try:
            public.verify(signature, data)
        except InvalidSignature:
            return False
        return True

    @staticmethod
    def get_fingerprint(public_key: bytes) -> str:
        """Return a human-friendly SHA-256 fingerprint (8 groups of 4 hex chars)."""
        digest = hashlib.sha256(public_key).hexdigest().upper()
        short = digest[:32]
        return " ".join(short[i : i + 4] for i in range(0, len(short), 4))

    @staticmethod
    def verify_fingerprint(fingerprint: str, public_key: bytes) -> bool:
        expected = UserIdentity.get_fingerprint(public_key)
        compact = "".join(fingerprint.upper().split())
        return compact == "".join(expected.split())

    def export_public_key(self, public_key: bytes) -> str:
        return base64.b64encode(public_key).decode("ascii")

    def import_public_key(self, key_b64: str) -> bytes:
        try:
            raw = _b64decode(key_b64)
        except Exception as exc:
            raise IdentityError("Invalid public key") from exc
        _public_key_from_bytes(raw)
        return raw


__all__ = ["IdentityError", "UserIdentity"]
