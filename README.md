# Klyvochat

Desktop communication app with P2P chat and WebRTC voice calls.

## Stack

- **UI:** PySide6 (Qt for Python)
- **P2P/Voice:** WebRTC via aiortc
- **Signaling:** WebSockets (Python client ↔ Node.js server)
- **Database:** SQLite (local) + MySQL/PostgreSQL (server)
- **Audio:** sounddevice

## Installation

### Client (Python)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Server (Node.js)

```bash
cd server
npm install
cp .env.example .env
# Edit .env with your settings
```

## Running

### Start the server

```bash
cd server
npm start
```

### Start the client

```bash
python run.py
```

## Project Structure

```
Klyvochat/
├── client/              # Python client
│   ├── ui/              # UI components
│   ├── core/            # Business logic
│   ├── network/         # P2P and signaling
│   ├── storage/         # Database
│   ├── security/        # Encryption
│   └── utils/           # Utilities
├── server/              # Node.js signaling server
│   └── src/
│       ├── routes/      # API routes
│       ├── websocket/    # WebSocket handlers
│       ├── middleware/   # Express middleware
│       └── database/    # DB connection
├── data/                # Local SQLite and logs
└── tests/               # Test files
```

## License

MIT
