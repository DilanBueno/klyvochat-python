import express from 'express';
import cors from 'cors';
import { createServer } from 'http';
import { WebSocketServer } from 'ws';
import { config } from './config.js';
import { initDatabase } from './database/db.js';
import authRouter from './routes/auth.js';
import usersRouter from './routes/users.js';
import { handleWebSocketConnection } from './websocket/handler.js';
import { startHeartbeat } from './websocket/presence.js';

const app = express();

app.use(cors());
app.use(express.json());

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.use('/api/auth', authRouter);
app.use('/api/users', usersRouter);

const server = createServer(app);
const wss = new WebSocketServer({
  server,
  maxPayload: 1024 * 1024,
});

wss.on('connection', (socket) => {
  console.log('New WebSocket connection');
  handleWebSocketConnection(socket);
});

startHeartbeat(wss);

async function start() {
  try {
    await initDatabase(config);
    console.log('Database initialized');
  } catch (err) {
    console.error('Failed to initialize database:', err);
    process.exit(1);
  }

  server.listen(config.port, () => {
    console.log(`Server running on port ${config.port}`);
  });
}

start();

export { app, server, wss, start };
