# Klyvochat roadmap

What shipped in each milestone, and what's planned next.

## v0.1 — Foundation (Phases 0–3) ✅

- Project scaffolding: PySide6 client + Express/`ws` server, SQLite + SQLAlchemy 2.0,
  Hostinger deploy script
- Steam-style dark theme, frameless `FloatingWindow` base with fade animations,
  window manager, styled login window
- Full auth: register/login, JWT (15 min) + refresh (7 d) with refresh-on-401,
  `~/.klyvochat/auth.json` (`0600`), user repositories and search
- Presence system with heartbeats (client 25 s/10 s, server 30 s/60 s) and friend
  list: requests, accept/remove, live online/away/offline status

## v0.2 — P2P communication (Phases 4–5) ✅

- Signaling relay: pure pass-through `{type, payload}` dispatch, no SDP inspection
- WebRTC sessions with in-band ICE, one session per peer, reconnect + offline queue
- Text chat over DataChannel: SQLite history, typing indicators, read receipts,
  idempotent `msg_id` delivery

## v0.3 — Voice calls (Phase 6) ✅

- `sounddevice` capture → aiortc `AudioTrack` → peer connection
- Call window with mute/speaker controls, incoming-call popup, device selection
- `CallManager` state machine (`call_offer`/`answer`/`reject`/`end`/`mute`)

## v0.4 — Security (Phase 7) ✅

- Per-device X25519 identity keys, in-band `key_exchange`, AES-256-GCM per
  conversation, ciphertext stored locally with `encrypted` flag
- Fingerprint dialog for out-of-band contact verification

## v0.5 — Desktop polish (Phases 8–9) ✅

- System-tray icon with unread badge, toast notifications, minimize-to-tray
- Settings window (account, friends, chat, voice, appearance) persisted to SQLite
- Profile popup, light theme + accent colors, window opacity, chat font size,
  conversation backup (JSON export)
- 45 automated tests (auth, P2P, messaging, voice, E2E crypto, notifications,
  settings) running headless in CI

## Future — advanced features (Phase 10) 🔲

- **Group chats** — WebRTC mesh (up to ~10 peers) or SFU for larger groups
- **File transfer** — chunked DataChannel sends with SHA-256 verification, drag & drop
- **Video calls** — camera tracks, picture-in-picture, bandwidth adaptation
- **LAN discovery** — mDNS/DNS-SD (`zeroconf`) for serverless local peers
- **Push notifications** — FCM for messages/calls while the app is closed
