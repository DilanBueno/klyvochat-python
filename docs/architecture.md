# Klyvochat architecture

```
┌─────────────────────────────┐            ┌─────────────────────────────┐
│  Client A (PySide6)         │            │  Client B (PySide6)         │
│  AppController              │            │  AppController              │
│   ├─ AuthManager (JWT)      │            │   ├─ AuthManager (JWT)      │
│   ├─ SignalingClient (ws) ──┼────────┐   │   ├─ SignalingClient (ws) ──┼────────┐
│   ├─ P2PManager / WebRTC ───┼────┐   │   │   ├─ P2PManager / WebRTC ───┼────┐   │
│   ├─ MessageManager (E2E)   │    │   │   │   ├─ MessageManager (E2E)   │    │   │
│   └─ SQLite (history/keys)  │    │   │   │   └─ SQLite (history/keys)  │    │   │
└─────────────────────────────┘    │   │   └─────────────────────────────┘    │   │
         media + DataChannel ──────┘   │            ▲                         │   │
              (direct P2P)             │            │                         │   │
                                       ▼            │                         ▼   │
                              ┌─────────────────────────────────┐              │
                              │  Server (Node.js: Express + ws) │ ◄────────────┘
                              │   REST: /auth /users /friends   │   signaling only
                              │   WS: relay {type, payload}     │   (pass-through)
                              │   MySQL/PostgreSQL              │
                              └─────────────────────────────────┘
```

The server is a **pure signaling relay**: it authenticates the WebSocket with the JWT,
routes `{type, payload}` envelopes between users, and tracks presence. It never inspects
SDP contents and never holds E2E keys. Voice media and chat DataChannels flow directly
between peers.

## Client modules (`client/`)

| Module | Responsibility |
| ------ | -------------- |
| `main.py` — `AppController` | owns AuthManager, SignalingClient, FriendManager, PresenceManager; async work via `qasync.QEventLoop`, never blocks the UI thread |
| `core/auth.py` | register/login/refresh/logout; tokens in `~/.klyvochat/auth.json` (`0600`); refresh-on-401 |
| `core/friends.py` | friend requests, accept/remove, optional auto-accept |
| `core/presence.py` | heartbeat-driven status, `PresenceManager` fan-out to UI |
| `core/messaging.py` | `MessageManager`: send/receive, typing + read receipts, offline queue, E2E seal/open |
| `core/voice.py` | `AudioStream` (sounddevice), `AudioTrack` (aiortc), `CallManager` state machine |
| `network/signaling_client.py` | WS client, reconnect with backoff, 25 s heartbeat / 10 s timeout |
| `network/webrtc_session.py` | `RTCPeerConnection` wrapper, in-band ICE in SDP, DataChannel events |
| `network/p2p_manager.py` | one session per peer, routes call/message signaling envelopes |
| `security/keys.py` | X25519 identity keypair per device, persisted locally |
| `security/encryption.py` | per-conversation AES-256-GCM seal/open |
| `security/identity.py` | key fingerprints for out-of-band verification |
| `storage/` | SQLAlchemy 2.0 models + repositories (users, friends, messages, keys, settings) |
| `ui/` | `FloatingWindow` base (frameless + fade), windows, widgets, `ThemeManager` |

## Auth flow

1. `POST /auth/register` (bcrypt hash stored) → `POST /auth/login` returns
   `{access_token (15 min), refresh_token (7 d)}`.
2. Client stores tokens in `~/.klyvochat/auth.json` and opens the WS with
   `Authorization: Bearer <access>`.
3. On 401 the client refreshes (`POST /auth/refresh`) and retries once.

## Signaling protocol

Every WS frame is JSON `{type, payload}`. Server-side dispatch lives in
`server/src/websocket/handler.js`; message types:

- `presence` — heartbeat + status broadcast (server: 30 s interval / 60 s timeout)
- `friend_request` / `friend_accept` / `friend_remove` — friendship lifecycle
- `call_offer` / `call_answer` / `call_ice` (not used — ICE is in-band) /
  `call_reject` / `call_end` / `call_mute`
- `webrtc_offer` / `webrtc_answer` — DataChannel session establishment
- `message` — ciphertext envelope `{ciphertext, nonce, tag}` + `encrypted` flag
- `key_exchange` — X25519 public-key publication per conversation
- `typing` / `read_receipt` — chat UX signals

## P2P session establishment (chat)

1. A creates `WebRTCSession`, opens a DataChannel, produces an offer (ICE gathered
   in-band into the SDP) and sends `webrtc_offer` via the server relay.
2. B sets the remote description, answers, sends `webrtc_answer` back through the relay.
3. On `connectionstatechange == connected`, both sides emit `peer_connected`; the
   `P2PManager` flushes any queued messages.
4. Plaintext path (pre-E2E or fallback): JSON straight through the DataChannel.
   Encrypted path: `MessageManager` seals with the conversation key first (see below).

## Voice call flow

1. A: `CallManager.start_call(peer)` → `call_offer` relayed; B shows `IncomingCallWidget`.
2. B accepts → `call_answer`; both create audio sessions (`AudioStream` →
   `AudioTrack` → `RTCPeerConnection.addTrack`).
3. During the call, `call_mute` toggles `AudioTrack.enabled`; `call_end`/`call_reject`
   tears down the `RTCPeerConnection` and closes tracks/streams.
4. Late-join audio (remote track arriving before the call window accepts) is buffered
   until the UI attaches, so no first-second clipping occurs.

## End-to-end encryption

1. First run generates an X25519 identity keypair (`security/keys.py`), stored in SQLite.
2. On first message to a peer, the client sends `key_exchange` with its public key and
   derives the shared secret via X25519 + HKDF once the peer's key arrives.
3. Every message is sealed with AES-256-GCM (fresh 96-bit nonce); the envelope carries
   `{ciphertext, nonce, tag}` and `encrypted: true`. The local DB stores the ciphertext.
4. The profile/settings UI shows the conversation fingerprint (`security/identity.py`)
   so both sides can verify keys over a trusted channel.

## Storage

- **Client** — SQLite at `data/klyvochat.db`: users, friends (+migrated columns),
  messages (ciphertext + `encrypted` flag + `msg_id` for idempotency), keypairs,
  settings. WAL-friendly `session_factory`; `init_db()` auto-creates `data/`.
- **Server** — MySQL/PostgreSQL via `mysql2`: users, friendships, refresh tokens.
  Exits on DB init failure (fail-fast).
