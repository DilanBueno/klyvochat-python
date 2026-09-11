from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Optional
import httpx
from jose import jwt

from config import settings
from client.storage.repositories import UserRepository, UserLocal


class AuthError(Exception):
    pass


class AuthManager:
    def __init__(self) -> None:
        self._auth_dir = Path.home() / ".klyvochat"
        self._auth_file = self._auth_dir / "auth.json"
        self._user_repo = UserRepository()
        self._token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._current_user: Optional[UserLocal] = None
        self._load_tokens()

    def _load_tokens(self) -> None:
        if not self._auth_file.exists():
            return
        try:
            data = json.loads(self._auth_file.read_text())
            self._token = data.get("token")
            self._refresh_token = data.get("refresh_token")
        except (json.JSONDecodeError, OSError):
            pass

    def _save_tokens(self, token: str, refresh_token: str) -> None:
        self._auth_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "token": token,
            "refresh_token": refresh_token,
        }
        self._auth_file.write_text(json.dumps(data))
        os.chmod(self._auth_file, stat.S_IRUSR | stat.S_IWUSR)

    def _clear_tokens(self) -> None:
        self._token = None
        self._refresh_token = None
        self._current_user = None
        if self._auth_file.exists():
            self._auth_file.unlink()

    def _build_api_url(self, path: str) -> str:
        base = settings.API_URL.rstrip("/")
        return f"{base}{path}"

    async def register(self, username: str, email: str, password: str) -> bool:
        url = self._build_api_url("/api/auth/register")
        payload = {"username": username, "email": email, "password": password}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
        except httpx.ConnectError:
            raise AuthError("Servidor indisponível. Verifique sua conexão.")
        except httpx.TimeoutException:
            raise AuthError("Tempo de conexão esgotado. Tente novamente.")

        if response.status_code != 201:
            error_msg = "Falha no registro"
            try:
                body = response.json()
                error_msg = body.get("error", error_msg)
            except Exception:
                pass
            raise AuthError(error_msg)

        data = response.json()
        self._token = data["token"]
        self._refresh_token = data["refresh_token"]
        self._save_tokens(self._token, self._refresh_token)
        self._save_user_locally(data.get("user", {}))
        return True

    async def login(self, email: str, password: str) -> bool:
        url = self._build_api_url("/api/auth/login")
        payload = {"email": email, "password": password}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
        except httpx.ConnectError:
            raise AuthError("Servidor indisponível. Verifique sua conexão.")
        except httpx.TimeoutException:
            raise AuthError("Tempo de conexão esgotado. Tente novamente.")

        if response.status_code != 200:
            error_msg = "Credenciais inválidas"
            try:
                body = response.json()
                error_msg = body.get("error", error_msg)
            except Exception:
                pass
            raise AuthError(error_msg)

        data = response.json()
        self._token = data["token"]
        self._refresh_token = data["refresh_token"]
        self._save_tokens(self._token, self._refresh_token)
        self._save_user_locally(data.get("user", {}))
        return True

    async def refresh_token(self) -> bool:
        if not self._refresh_token:
            return False

        url = self._build_api_url("/api/auth/refresh")
        payload = {"refresh_token": self._refresh_token}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
        except Exception:
            self._clear_tokens()
            return False

        if response.status_code != 200:
            self._clear_tokens()
            return False

        data = response.json()
        self._token = data["token"]
        self._save_tokens(self._token, self._refresh_token)
        return True

    def logout(self) -> None:
        self._clear_tokens()
        self._user_repo.clear_current()

    def get_token(self) -> Optional[str]:
        return self._token

    def get_refresh_token(self) -> Optional[str]:
        return self._refresh_token

    def is_authenticated(self) -> bool:
        if not self._token:
            return False
        try:
            payload = jwt.get_unverified_claims(self._token)
            if payload.get("exp"):
                from datetime import datetime, timezone
                exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                if datetime.now(timezone.utc) >= exp:
                    return False
            return True
        except Exception:
            return False

    def get_current_user(self) -> Optional[UserLocal]:
        if self._current_user:
            return self._current_user
        self._current_user = self._user_repo.get_current()
        return self._current_user

    def _save_user_locally(self, user_data: dict) -> None:
        if not user_data.get("id"):
            return
        user = UserLocal(
            id=str(user_data["id"]),
            username=user_data.get("username", ""),
            email=user_data.get("email", ""),
            display_name=user_data.get("username", ""),
        )
        self._user_repo.save_current(user)
        self._current_user = user
