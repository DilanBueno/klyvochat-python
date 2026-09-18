from __future__ import annotations

import base64
import json
import os
from datetime import UTC
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from client.storage.models import KeyPair
from client.storage.repositories import KeyPairRepository, SettingsRepository

PBKDF2_ITERATIONS = 200_000
PRIVATE_KEY_VERSION = 1
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
DEFAULT_ROTATION_DAYS = 90
ROTATION_SETTING_KEY = "key_rotation_days"


class KeyManagerError(Exception):
    """Raised when a key operation cannot be performed."""


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _derive_encryption_key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(password.encode("utf-8"))


def _encrypt_private_key(
    private_bytes: bytes, password: str, iterations: int = PBKDF2_ITERATIONS
) -> str:
    salt = os.urandom(SALT_SIZE)
    key = _derive_encryption_key(password, salt, iterations)
    nonce = os.urandom(NONCE_SIZE)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    ciphertext = encryptor.update(private_bytes) + encryptor.finalize()
    payload = {
        "version": PRIVATE_KEY_VERSION,
        "iterations": iterations,
        "salt": _b64encode(salt),
        "nonce": _b64encode(nonce),
        "tag": _b64encode(encryptor.tag),
        "ciphertext": _b64encode(ciphertext),
    }
    return _b64encode(json.dumps(payload).encode("utf-8"))


def _decrypt_private_key(encrypted: str, password: str) -> bytes:
    try:
        payload = json.loads(_b64decode(encrypted).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise KeyManagerError("Invalid stored private key") from exc
    iterations = int(payload.get("iterations", PBKDF2_ITERATIONS))
    salt = _b64decode(payload["salt"])
    key = _derive_encryption_key(password, salt, iterations)
    nonce = _b64decode(payload["nonce"])
    tag = _b64decode(payload["tag"])
    ciphertext = _b64decode(payload["ciphertext"])
    try:
        decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    except Exception as exc:
        raise KeyManagerError("Wrong password or corrupted key") from exc


class KeyManager:
    """Generates and stores an X25519 keypair.

    The private key is stored in SQLite encrypted with a key derived from the
    user's password (PBKDF2 + AES-GCM). While unlocked, the raw private key is
    kept in memory only.
    """

    def __init__(
        self,
        user_id: str | None = None,
        *,
        key_repo: KeyPairRepository | None = None,
        settings_repo: SettingsRepository | None = None,
        key_rotation_days: int = DEFAULT_ROTATION_DAYS,
        current_user_id: str | None = None,
    ) -> None:
        if current_user_id is not None:
            user_id = current_user_id
        self._user_id = str(user_id) if user_id else None
        self._key_repo = key_repo if key_repo is not None else KeyPairRepository()
        self._settings_repo = settings_repo if settings_repo is not None else SettingsRepository()
        self._key_rotation_days = key_rotation_days
        self._keypair: Any = None
        self._private_key: bytes | None = None
        self._public_key: bytes | None = None
        self.user_id = self._user_id

    @property
    def is_unlocked(self) -> bool:
        return self._private_key is not None

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate a fresh X25519 keypair, returning ``(public, private)``."""
        private_key = X25519PrivateKey.generate()
        public_bytes = private_key.public_key().public_bytes_raw()
        private_bytes = private_key.private_bytes_raw()
        return public_bytes, private_bytes

    def has_keys(self) -> bool:
        return self._load_keypair() is not None

    def get_public_key(self) -> bytes | None:
        keypair = self._load_keypair()
        if keypair is None:
            return None
        if self._public_key is None:
            self._public_key = _b64decode(keypair.public_key)
        return self._public_key

    def get_private_key(self, password: str | None = None) -> bytes | None:
        """Return the decrypted private key.

        Requires the key to be unlocked (via :meth:`unlock`) or a ``password``
        to unlock on demand. Returns ``None`` when locked.
        """
        if self._private_key is not None:
            return self._private_key
        if password is None:
            return None
        keypair = self._load_keypair()
        if keypair is None:
            return None
        self._private_key = _decrypt_private_key(keypair.private_key, password)
        return self._private_key

    def ensure_keys(self, password: str) -> bytes:
        """Generate and persist keys if missing; returns the public key."""
        keypair = self._load_keypair()
        if keypair is not None:
            return self.get_public_key() or b""
        public_bytes, private_bytes = self.generate_keypair()
        self.save_keys(public_bytes, private_bytes, password)
        return public_bytes

    def save_keys(self, public_key: bytes, private_key: bytes, password: str) -> None:
        """Persist the keypair with the private key encrypted by ``password``."""
        user_id = self._get_user_id()
        encrypted = _encrypt_private_key(private_key, password)
        self._key_repo.delete_for_user(user_id)
        keypair = KeyPair(
            user_id=user_id,
            public_key=_b64encode(public_key),
            private_key=encrypted,
        )
        self._key_repo.save_keypair(keypair)
        self._keypair = keypair
        self._public_key = public_key
        self._private_key = private_key

    def unlock(self, password: str) -> bool:
        keypair = self._load_keypair()
        if keypair is None:
            return False
        try:
            self._private_key = _decrypt_private_key(keypair.private_key, password)
        except KeyManagerError:
            return False
        self._public_key = _b64decode(keypair.public_key)
        return True

    def lock(self) -> None:
        self._private_key = None
        self._public_key = None

    def export_public_key(self) -> str:
        public_key = self.get_public_key()
        if public_key is None:
            raise KeyManagerError("No keys available")
        return _b64encode(public_key)

    @staticmethod
    def import_peer_public_key(key_b64: str) -> bytes:
        try:
            raw = _b64decode(key_b64)
        except Exception as exc:
            raise KeyManagerError("Invalid public key") from exc
        try:
            X25519PublicKey.from_public_bytes(raw)
        except Exception as exc:
            raise KeyManagerError("Invalid X25519 public key") from exc
        return raw

    def should_rotate(self) -> bool:
        """Return ``True`` when the keypair is older than the rotation window."""
        keypair = self._load_keypair()
        if keypair is None or keypair.created_at is None:
            return False
        from datetime import datetime, timedelta

        try:
            stored = int(self._settings_repo.get(ROTATION_SETTING_KEY, "") or 0)
            days = stored or self._key_rotation_days
        except ValueError:
            days = self._key_rotation_days
        created = keypair.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return datetime.now(UTC) - created >= timedelta(days=days)

    def delete_keys(self) -> None:
        self._key_repo.delete_for_user(self._get_user_id())
        self._keypair = None
        self._private_key = None
        self._public_key = None

    def set_rotation_days(self, days: int) -> None:
        self._settings_repo.set(ROTATION_SETTING_KEY, str(int(days)))

    def _load_keypair(self) -> Any | None:
        user_id = self._get_user_id()
        if self._keypair is not None and getattr(self._keypair, "user_id", None) == user_id:
            return self._keypair
        self._keypair = self._key_repo.get_for_user(user_id)
        return self._keypair

    def _get_user_id(self) -> str:
        if self._user_id:
            return self._user_id
        from client.storage.repositories import UserRepository

        user = UserRepository().get_current()
        if user is not None and getattr(user, "id", None):
            self._user_id = str(user.id)
            self.user_id = self._user_id
            return self._user_id
        raise KeyManagerError("No user available")


__all__ = [
    "DEFAULT_ROTATION_DAYS",
    "KeyManager",
    "KeyManagerError",
    "ROTATION_SETTING_KEY",
]
