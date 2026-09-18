from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from client.core import auth as auth_module
from client.core.auth import AuthError, AuthManager
from client.storage.database import Base
from client.storage.repositories import UserRepository

USER = {
    "id": "user-1",
    "username": "dilan",
    "email": "dilan@example.com",
}


class FakeResponse:
    def __init__(self, status_code: int, json_data: Any):
        self.status_code = status_code
        self._json_data = json_data

    def json(self) -> Any:
        return self._json_data


class FakeClient:
    def __init__(self, responses: list[FakeResponse], error: Exception | None = None):
        self.responses = responses
        self.error = error
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def post(self, url: str, json: dict[str, Any] | None = None, timeout: Any = None):
        self.calls.append((url, json or {}))
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)


@pytest.fixture
def manager(tmp_path):
    # Isolated temp DB with the real schema: the suite must pass on a fresh
    # checkout where data/klyvochat.db does not exist (e.g. CI).
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _factory():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    auth = AuthManager()
    auth._auth_dir = tmp_path
    auth._auth_file = tmp_path / "auth.json"
    auth._user_repo = UserRepository(session_factory=_factory)
    auth._save_user_locally = lambda data: None
    return auth


def _patch_client(monkeypatch, responses=None, error=None) -> FakeClient:
    fake = FakeClient(responses or [], error=error)
    monkeypatch.setattr(auth_module.httpx, "AsyncClient", lambda: fake)
    return fake


async def test_register_success(manager, monkeypatch, tmp_path):
    _patch_client(
        monkeypatch,
        [FakeResponse(201, {"token": "jwt-1", "refresh_token": "refresh-1", "user": USER})],
    )
    assert await manager.register("dilan", "dilan@example.com", "secret12") is True
    assert manager.get_token() == "jwt-1"
    assert (tmp_path / "auth.json").exists()
    assert (tmp_path / "auth.json").stat().st_mode & 0o777 == 0o600


async def test_login_success(manager, monkeypatch):
    fake = _patch_client(
        monkeypatch,
        [FakeResponse(200, {"token": "jwt-1", "refresh_token": "refresh-1", "user": USER})],
    )
    assert await manager.login("dilan@example.com", "secret12") is True
    assert manager.get_token() == "jwt-1"
    assert fake.calls[0][0].endswith("/api/auth/login")


async def test_login_invalid_credentials(manager, monkeypatch):
    _patch_client(monkeypatch, [FakeResponse(400, {"error": "Credenciais inválidas"})])
    with pytest.raises(AuthError) as exc:
        await manager.login("dilan@example.com", "wrong")
    assert "Credenciais" in str(exc.value)


async def test_login_server_unavailable(manager, monkeypatch):
    _patch_client(monkeypatch, error=httpx.ConnectError("boom"))
    with pytest.raises(AuthError) as exc:
        await manager.login("dilan@example.com", "secret12")
    assert "Servidor indisponível" in str(exc.value)


async def test_login_timeout(manager, monkeypatch):
    _patch_client(monkeypatch, error=httpx.TimeoutException("slow"))
    with pytest.raises(AuthError) as exc:
        await manager.login("dilan@example.com", "secret12")
    assert "Tempo" in str(exc.value)


async def test_refresh_token_success(manager, monkeypatch):
    manager._token = "old"
    manager._refresh_token = "refresh-1"
    _patch_client(monkeypatch, [FakeResponse(200, {"token": "jwt-new"})])
    assert await manager.refresh_token() is True
    assert manager.get_token() == "jwt-new"
    assert manager.get_refresh_token() == "refresh-1"


async def test_refresh_token_failure_clears(manager, monkeypatch, tmp_path):
    manager._token = "old"
    manager._refresh_token = "refresh-1"
    manager._save_tokens("old", "refresh-1")
    _patch_client(monkeypatch, [FakeResponse(401, {"error": "invalid"})])
    assert await manager.refresh_token() is False
    assert manager.get_token() is None
    assert not (tmp_path / "auth.json").exists()


def test_logout_clears_tokens(manager, tmp_path):
    manager._save_tokens("jwt", "refresh")
    manager.logout()
    assert manager.get_token() is None
    assert not (tmp_path / "auth.json").exists()


def test_is_authenticated(manager):
    token = jwt.encode(
        {"sub": "user-1", "exp": int(time.time()) + 3600}, "secret", algorithm="HS256"
    )
    manager._token = token
    assert manager.is_authenticated() is True

    expired = jwt.encode(
        {"sub": "user-1", "exp": int(time.time()) - 3600}, "secret", algorithm="HS256"
    )
    manager._token = expired
    assert manager.is_authenticated() is False
