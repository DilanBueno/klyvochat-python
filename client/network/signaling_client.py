from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import websockets
from websockets.exceptions import ConnectionClosed

from config import settings

logger = logging.getLogger(__name__)

Listener = Callable[[Any], Any]


class HeartbeatTimeoutError(TimeoutError):
    pass


HeartbeatTimeout = HeartbeatTimeoutError


class SignalingClient:
    def __init__(
        self,
        url: str | Any | None = None,
        token: str | Any | None = None,
        *,
        token_provider: Callable[[], str | Awaitable[str]] | Any | None = None,
        auth_manager: Any | None = None,
        jwt_token: str | None = None,
        max_reconnect_attempts: int = 10,
        reconnect_attempts: int | None = None,
        heartbeat_interval: float = 25.0,
        heartbeat_timeout: float = 10.0,
        websocket_connect: Callable[..., Any] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if reconnect_attempts is not None:
            max_reconnect_attempts = reconnect_attempts
        if max_reconnect_attempts < 0:
            raise ValueError("max_reconnect_attempts must be non-negative")
        if heartbeat_interval <= 0 or heartbeat_timeout <= 0:
            raise ValueError("heartbeat intervals must be positive")

        if token is None and jwt_token is not None:
            token = jwt_token
        if token is None and hasattr(url, "get_token"):
            token_provider = url
            url = None
        elif token is None and isinstance(url, str) and not url.startswith(("ws://", "wss://")):
            token = url
            url = None
        elif token is not None and hasattr(token, "get_token"):
            token_provider = token
            token = None

        self.url = url or settings.SIGNALING_URL
        self._token = token
        self._token_provider = token_provider or auth_manager
        self._websocket_connect = websocket_connect or websockets.connect
        self._sleep = sleep or asyncio.sleep
        self._max_reconnect_attempts = max_reconnect_attempts
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_timeout = heartbeat_timeout

        self._listeners: dict[str, list[Listener]] = defaultdict(list)
        self._ws: Any | None = None
        self._manager_task: asyncio.Task[None] | None = None
        self._receiver_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._authenticated = asyncio.Event()
        self._pong_received = asyncio.Event()
        self._auth_payload: dict[str, Any] | None = None
        self._auth_error: BaseException | None = None

        self._stopping = True
        self._last_error: BaseException | None = None
        self._fatal_error: BaseException | None = None

    @property
    def ws(self) -> Any | None:
        return self._ws

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._socket_is_open(self._ws)

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated.is_set() and self.is_connected

    @property
    def auth_payload(self) -> dict[str, Any] | None:
        return dict(self._auth_payload) if self._auth_payload is not None else None

    def _socket_is_open(self, ws: Any) -> bool:
        closed = getattr(ws, "closed", None)
        if closed is not None:
            return not closed
        return bool(getattr(ws, "open", True))

    def on(self, event: str, callback: Listener) -> Listener:
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)
        return callback

    def off(self, event: str, callback: Listener) -> None:
        callbacks = self._listeners.get(event, [])
        if callback in callbacks:
            callbacks.remove(callback)
        if not callbacks:
            self._listeners.pop(event, None)

    async def connect(self) -> None:
        if self.is_authenticated:
            return
        if self._manager_task is not None and not self._manager_task.done():
            await self._wait_for_connection()
            if not self._authenticated.is_set():
                raise ConnectionError("Signaling authentication failed")
            return

        self._stopping = False
        self._connected.clear()
        self._authenticated.clear()
        self._pong_received.clear()
        self._auth_payload = None
        self._auth_error = None
        self._last_error = None
        self._fatal_error = None
        self._manager_task = asyncio.create_task(self._connection_manager())
        await self._wait_for_connection()
        if not self._authenticated.is_set():
            raise ConnectionError("Signaling authentication failed")

    async def disconnect(self) -> None:
        self._stopping = True
        self._connected.clear()
        self._authenticated.clear()
        self._auth_payload = None
        self._auth_error = None
        ws = self._ws
        self._ws = None

        if ws is not None:
            await self._close_socket(ws)

        tasks = [
            task
            for task in (self._receiver_task, self._heartbeat_task)
            if task is not None and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._receiver_task = None
        self._heartbeat_task = None

        current = asyncio.current_task()
        if self._manager_task is not None and self._manager_task is not current:
            self._manager_task.cancel()
            await asyncio.gather(self._manager_task, return_exceptions=True)
        self._manager_task = None

    async def send(self, type: str, payload: Any = None) -> Any:
        if not self.is_authenticated:
            raise ConnectionError("Signaling client is not authenticated")
        ws = self._ws
        if ws is None or not self._socket_is_open(ws):
            raise ConnectionError("Signaling client is not connected")
        message = {"type": type, "payload": payload}
        return await ws.send(json.dumps(message))

    async def _wait_for_connection(self) -> None:
        if self._manager_task is None:
            return
        event_waiter = asyncio.create_task(self._connected.wait())
        try:
            done, _ = await asyncio.wait(
                {event_waiter, self._manager_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if event_waiter not in done and self._manager_task in done:
                if self._fatal_error is not None:
                    raise self._fatal_error
                if self._last_error is not None:
                    raise ConnectionError(str(self._last_error))
                raise ConnectionError("Signaling connection failed")
        finally:
            if not event_waiter.done():
                event_waiter.cancel()
                await asyncio.gather(event_waiter, return_exceptions=True)

    async def _connection_manager(self) -> None:
        reconnect_attempt = 0
        while not self._stopping:
            ws: Any | None = None
            try:
                token = await self._resolve_token()
                ws = await self._open_connection(token)
                if self._stopping:
                    await self._close_socket(ws)
                    break

                self._ws = ws
                self._pong_received.clear()
                self._receiver_task = asyncio.create_task(self._receive_loop(ws))
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))

                try:
                    await ws.send(json.dumps({"type": "auth", "payload": {"token": token}}))
                    await asyncio.wait_for(self._authenticated.wait(), timeout=10)
                except TimeoutError:
                    self._last_error = ConnectionError(
                        "Timed out while authenticating signaling connection"
                    )
                    self._fatal_error = self._last_error
                    await self._close_socket(ws)
                    break
                except Exception as exc:
                    self._last_error = exc
                    self._fatal_error = exc
                    await self._close_socket(ws)
                    break

                if self._auth_error is not None:
                    self._fatal_error = self._auth_error
                    await self._close_socket(ws)
                    break

                self._connected.set()
                reconnect_attempt = 0

                done, _ = await asyncio.wait(
                    {self._receiver_task, self._heartbeat_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    if task is self._heartbeat_task:
                        try:
                            task.result()
                        except HeartbeatTimeout:
                            self._last_error = HeartbeatTimeout("Signaling heartbeat timed out")
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            self._last_error = exc
                    elif task is self._receiver_task:
                        try:
                            task.result()
                        except ConnectionClosed:
                            pass
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            self._last_error = exc

                if not self._stopping and ws is not None:
                    await self._close_socket(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = exc
            finally:
                if self._ws is ws:
                    self._ws = None
                self._connected.clear()
                self._authenticated.clear()
                if ws is not None:
                    await self._close_socket(ws)

            if self._stopping:
                break
            if reconnect_attempt >= self._max_reconnect_attempts:
                self._fatal_error = self._last_error or ConnectionError(
                    "Signaling reconnection attempts exhausted"
                )
                break

            delay = min(2**reconnect_attempt, 30)
            reconnect_attempt += 1
            await self._sleep(delay)

    async def _open_connection(self, token: str) -> Any:
        parameters = {}
        try:
            parameters = inspect.signature(self._websocket_connect).parameters
        except (TypeError, ValueError):
            pass
        accepts_kwargs = any(
            parameter.kind == parameter.VAR_KEYWORD for parameter in parameters.values()
        )
        headers_name = None
        if "additional_headers" in parameters:
            headers_name = "additional_headers"
        elif "extra_headers" in parameters:
            headers_name = "extra_headers"
        elif accepts_kwargs:
            headers_name = "extra_headers"

        uri = self.url
        connect_kwargs: dict[str, Any] = {}
        if headers_name is not None:
            connect_kwargs[headers_name] = {"Authorization": f"Bearer {token}"}
        else:
            uri = self._with_token_query(token)
        if "ping_interval" in parameters or accepts_kwargs:
            connect_kwargs["ping_interval"] = None
        return await self._websocket_connect(uri, **connect_kwargs)

    def _with_token_query(self, token: str) -> str:
        parts = urlsplit(self.url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        if not any(key in {"token", "access_token", "jwt"} for key, _ in query):
            query.append(("token", token))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )

    async def _resolve_token(self) -> str:
        source = self._token_provider
        if source is None:
            value = self._token
        elif callable(source):
            value = source()
        else:
            value = source.get_token()
        if inspect.isawaitable(value):
            value = await value
        if not value:
            raise ValueError("A JWT is required to connect to signaling")
        return str(value)

    async def _receive_loop(self, ws: Any) -> None:
        async for message in ws:
            await self._handle_message(ws, message)

    async def _handle_message(self, ws: Any, message: Any) -> None:
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            logger.warning("Ignoring invalid signaling message")
            return
        if not isinstance(data, dict):
            return

        event_type = data.get("type")
        payload = data.get("payload", data)
        if event_type == "pong":
            self._pong_received.set()
        elif event_type == "ping":
            await ws.send(json.dumps({"type": "pong", "payload": {}}))
        elif event_type == "auth_ok":
            self._auth_payload = payload if isinstance(payload, dict) else {}
            self._auth_error = None
            self._authenticated.set()
        elif event_type in {"auth_error", "error"} and not self._authenticated.is_set():
            detail = (
                payload.get("message", "Signaling authentication failed")
                if isinstance(payload, dict)
                else str(payload)
            )
            self._auth_error = ConnectionError(detail)
            self._authenticated.set()

        if event_type:
            await self._emit(str(event_type), payload)

    async def _heartbeat_loop(self, ws: Any) -> None:
        while not self._stopping:
            await self._sleep(self._heartbeat_interval)
            if self._ws is not ws or not self._socket_is_open(ws):
                return
            self._pong_received.clear()
            ping = getattr(ws, "ping", None)
            if callable(ping):
                pong = ping()
                if inspect.isawaitable(pong):
                    pong_task = asyncio.ensure_future(pong)
                    json_pong_task = asyncio.create_task(self._pong_received.wait())
                    try:
                        done, _ = await asyncio.wait_for(
                            asyncio.wait(
                                {pong_task, json_pong_task},
                                return_when=asyncio.FIRST_COMPLETED,
                            ),
                            timeout=self._heartbeat_timeout,
                        )
                    except TimeoutError as exc:
                        pong_task.cancel()
                        json_pong_task.cancel()
                        await asyncio.gather(pong_task, json_pong_task, return_exceptions=True)
                        raise HeartbeatTimeout from exc
                    if json_pong_task in done:
                        pong_task.cancel()
                        await asyncio.gather(pong_task, return_exceptions=True)
                    else:
                        await pong_task
                    json_pong_task.cancel()
                    await asyncio.gather(json_pong_task, return_exceptions=True)
                    continue
            await ws.send(json.dumps({"type": "ping", "payload": {}}))
            try:
                await asyncio.wait_for(self._pong_received.wait(), timeout=self._heartbeat_timeout)
            except TimeoutError as exc:
                raise HeartbeatTimeout from exc

    async def _emit(self, event: str, payload: Any) -> None:
        for callback in list(self._listeners.get(event, [])):
            try:
                result = self._call_listener(callback, event, payload)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("Signaling event listener failed: %s", event)

    def _call_listener(self, callback: Listener, event: str, payload: Any) -> Any:
        try:
            parameters = list(inspect.signature(callback).parameters.values())
            positional = [
                parameter
                for parameter in parameters
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            if parameters and parameters[-1].kind == parameters[-1].VAR_POSITIONAL:
                return callback(event, payload)
            if len(positional) == 0:
                return callback()
            if len(positional) >= 2:
                return callback(event, payload)
        except (TypeError, ValueError):
            pass
        return callback(payload)

    async def _close_socket(self, ws: Any) -> None:
        try:
            if self._socket_is_open(ws):
                await ws.close()
        except Exception:
            logger.debug("Error while closing signaling socket", exc_info=True)


__all__ = ["HeartbeatTimeout", "HeartbeatTimeoutError", "SignalingClient"]
