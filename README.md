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

### Start the server (local)

```bash
cd server
npm start
```

### Start the client

```bash
python run.py
```

## Deploy na Hostinger

### Pré-requisitos

- Plano Business/Cloud na Hostinger (suporte a Node.js)
- Domínio configurado (ex.: `seudominio.com`)
- SSL/HTTPS ativado (a Hostinger fornece gratuitamente)

### 1. Preparar o servidor

```bash
# Na raiz do projeto, gere o zip do servidor:
bash deploy.sh
```

O script cria `server/klyvochat-server.zip` excluindo `node_modules/` e `.git/`.

### 2. Fazer upload via hPanel

1. Acesse o hPanel → **Websites** → **Node.js web app**
2. Faça upload do arquivo `klyvochat-server.zip`
3. Configurações de build:
   - **Entry file:** `src/index.js`
   - **Node.js version:** `22`
4. Clique em **Deploy** / **Restart**

### 3. Configurar variáveis de ambiente

No hPanel, em **Environment variables**, defina:

```
PORT=8080
NODE_ENV=production
JWT_SECRET=<troque-por-um-valor-seguro>
JWT_EXPIRES_IN=15m
REFRESH_EXPIRES_IN=7d
```

> As variáveis de banco (`DB_*`) são configuradas automaticamente pelo painel da Hostinger.

### 4. Configurar o cliente Python

Crie o arquivo `.env` na raiz do projeto com as URLs do seu domínio:

```
SIGNALING_URL=wss://seudominio.com
API_URL=https://seudominio.com
```

O cliente lê essas variáveis automaticamente (via `pydantic-settings` em `config.py`).

### 5. Verificar

```bash
curl https://seudominio.com/health
```

Esperado: `{"status":"ok"}`

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
