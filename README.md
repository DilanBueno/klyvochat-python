# Klyvochat

[![CI](https://github.com/DilanBueno/klyvochat-python/actions/workflows/ci.yml/badge.svg)](https://github.com/DilanBueno/klyvochat-python/actions/workflows/ci.yml)

Desktop messenger with **P2P end-to-end encrypted chat** and **WebRTC voice calls**.

A PySide6 (Qt) desktop client talks to a lightweight Node.js signaling server over
WebSockets. Text messages and voice media flow **directly between peers** — the server
only relays signaling and stores accounts, friendships and presence. Local history lives
in SQLite; the server persists to MySQL/PostgreSQL.

## Features

- **Accounts & auth** — register, login, JWT access (15 min) + refresh (7 d) tokens with
  automatic refresh-on-401; tokens stored with `0600` permissions
- **Friends & presence** — send/accept/remove friend requests, live online/away/offline
  status with heartbeat, auto-accept option
- **P2P chat** — WebRTC DataChannel messaging with typing indicators, read receipts,
  offline queue and local SQLite history
- **Voice calls** — WebRTC audio calls with mute/unmute, device selection, mic test with
  live level meter, incoming-call popup
- **End-to-end encryption** — X25519 key exchange + AES-256-GCM per conversation, with a
  fingerprint dialog to verify contacts out-of-band
- **Desktop experience** — frameless floating windows, system-tray icon with unread badge,
  toast notifications, dark/light themes, accent colors, window opacity and chat font size
- **Settings & profile** — display name, password change dialog, conversation backup
  (JSON export), per-device voice configuration
- **Tests** — 45 automated tests (auth, P2P, messaging, voice, E2E crypto, notifications,
  settings) run headless in CI

## Stack

| Layer     | Tech                                                        |
| --------- | ----------------------------------------------------------- |
| UI        | PySide6 (Qt for Python), qasync event loop                  |
| P2P/Voice | WebRTC via aiortc, sounddevice                              |
| Signaling | WebSockets (`ws`) + Express (Node.js 22)                    |
| Databases | SQLite + SQLAlchemy 2.0 (client), MySQL/PostgreSQL (server) |
| Security  | `cryptography` (X25519, AES-GCM), JWT, bcrypt               |
| Quality   | pytest, ruff, black, GitHub Actions                         |

## Quickstart

### Client (Python 3.11+)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point SIGNALING_URL / API_URL at your server
python run.py
```

For local development against a server on the same machine:

```
SIGNALING_URL=ws://localhost:8080
API_URL=http://localhost:8080
```

### Server (Node.js 22)

```bash
cd server
npm install
cp .env.example .env   # set JWT_SECRET and DB_* (see server/.env.example)
npm start              # dev: npm run dev
curl http://localhost:8080/health   # expect {"status":"ok"}
```

### Tests & lint

```bash
python -m pytest -q
ruff check . && black --check .
```

## Security model

- Passwords are hashed with **bcrypt**; login returns a short-lived JWT plus a refresh token.
- Each device generates an **X25519** identity keypair on first run. Peers exchange public
  keys in-band and derive a shared secret; messages are sealed with **AES-256-GCM**.
- The fingerprint dialog lets both sides confirm they share the same key out-of-band.
- Signaling is a pure pass-through relay — the server never sees SDP contents or keys.

See [`docs/architecture.md`](docs/architecture.md) for sequence diagrams and module details.

## Project structure

```
klyvochat-python/
├── run.py                 # client entry point (QApplication + qasync loop)
├── config.py              # client settings (pydantic-settings, root .env)
├── client/
│   ├── main.py            # AppController: auth, signaling, friends, presence
│   ├── ui/                # FloatingWindow base, windows, widgets, themes
│   ├── core/              # auth, friends, messaging, voice, notifications
│   ├── network/           # signaling client, WebRTC session, P2P manager
│   ├── security/          # X25519 keys, AES-GCM, fingerprints
│   ├── storage/           # SQLite via SQLAlchemy 2.0 (models, repositories)
│   └── utils/             # logging
├── server/src/            # Express + ws on one port (routes, middleware, websocket)
├── tests/                 # pytest suite (asyncio_mode=auto)
├── docs/                  # architecture notes
└── deploy.sh              # builds a versioned server zip for Hostinger
```

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) for what shipped in each phase and what's planned next
(group chats, file transfer, screen sharing).

## License

MIT — see [LICENSE](LICENSE).
