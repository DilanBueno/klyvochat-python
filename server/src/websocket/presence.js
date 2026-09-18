import { getPool } from '../database/db.js';

export const VALID_STATUSES = new Set(['online', 'idle', 'dnd', 'offline']);
export const HEARTBEAT_INTERVAL_MS = 30_000;
export const HEARTBEAT_TIMEOUT_MS = 60_000;

const QUEUED_EVENT_TTL_MS = 30_000;
const MAX_QUEUED_EVENTS = 100;
const connectionsByUser = new Map();
const statusByUser = new Map();
const offlineEventQueue = new Map();
const socketRegistry = new Map();

export class PresenceManager {
  constructor(options = {}) {
    this.getFriendIds = options.getFriendIds || this.#getDefaultFriendIds.bind(this);
  }

  async addConnection(userId, socket) {
    if (!userId || !socket?.id) {
      throw new Error('userId and socket are required');
    }

    let socketIds = connectionsByUser.get(userId);
    const wasOffline = !socketIds || socketIds.size === 0;

    if (!socketIds) {
      socketIds = new Set();
      connectionsByUser.set(userId, socketIds);
    }

    socketIds.add(socket.id);
    socket.klyvochatUserId = userId;

    if (wasOffline) {
      statusByUser.set(userId, 'online');
      await this.broadcastToFriends(userId, {
        user_id: userId,
        status: 'online',
        online: true,
      });
    }

    return socketIds.size;
  }

  async removeConnection(socket) {
    const userId = socket.klyvochatUserId;
    if (!userId) {
      return 0;
    }

    const socketIds = connectionsByUser.get(userId);
    if (!socketIds) {
      return 0;
    }

    socketIds.delete(socket.id);

    if (socketIds.size > 0) {
      return socketIds.size;
    }

    connectionsByUser.delete(userId);
    statusByUser.set(userId, 'offline');
    await this.broadcastToFriends(userId, {
      user_id: userId,
      status: 'offline',
      online: false,
    });
    return 0;
  }

  async updateStatus(userId, status) {
    if (!VALID_STATUSES.has(status)) {
      throw new Error('Invalid presence status');
    }

    statusByUser.set(userId, status);
    const online = status !== 'offline' && this.isOnline(userId);
    await this.broadcastToFriends(userId, {
      user_id: userId,
      status,
      online,
    });
    return status;
  }

  isOnline(userId) {
    const socketIds = connectionsByUser.get(userId);
    return Boolean(socketIds?.size && statusByUser.get(userId) !== 'offline');
  }

  getStatus(userId) {
    return this.isOnline(userId) ? statusByUser.get(userId) || 'online' : 'offline';
  }

  getSocketIds(userId) {
    return [...(connectionsByUser.get(userId) || [])];
  }

  async getOnlineFriends(userId) {
    const friendIds = await this.getFriendIds(userId);
    return friendIds.filter((friendId) => this.isOnline(friendId));
  }

  async broadcastToFriends(userId, event) {
    const friendIds = await this.getFriendIds(userId);
    await Promise.allSettled(
      friendIds.map((friendId) => sendToUser(friendId, 'presence_update', event))
    );
  }

  async #getDefaultFriendIds(userId) {
    const pool = getPool();
    if (!pool) {
      return [];
    }

    const [rows] = await pool.query(
      `
        SELECT requester_id AS user_id FROM friendships
        WHERE addressee_id = ? AND status = 'accepted'
        UNION
        SELECT addressee_id AS user_id FROM friendships
        WHERE requester_id = ? AND status = 'accepted'
      `,
      [userId, userId]
    );
    return rows.map((row) => row.user_id);
  }
}

const presence = new PresenceManager();

export function sendToUser(userId, type, payload = {}) {
  const socketIds = presence.getSocketIds(userId);
  if (socketIds.length === 0) {
    queueEventForUser(userId, type, payload);
    return false;
  }

  const message = JSON.stringify({ type, payload });
  socketIds.forEach((socketId) => {
    const socket = socketRegistry.get(socketId);
    if (socket?.readyState === 1) {
      socket.send(message);
    }
  });
  return true;
}

export function registerSocket(socket) {
  socketRegistry.set(socket.id, socket);
}

export function unregisterSocket(socket) {
  socketRegistry.delete(socket.id);
}

export function getSocket(socketId) {
  return socketRegistry.get(socketId);
}

export function queueEventForUser(userId, type, payload = {}) {
  if (!userId) {
    return;
  }

  let queue = offlineEventQueue.get(userId);
  if (!queue) {
    queue = [];
    offlineEventQueue.set(userId, queue);
  }

  queue.push({ type, payload, queuedAt: Date.now() });
  if (queue.length > MAX_QUEUED_EVENTS) {
    offlineEventQueue.set(userId, queue.slice(-MAX_QUEUED_EVENTS));
  }
}

export function drainQueuedEvents(userId) {
  const queue = offlineEventQueue.get(userId);
  if (!queue?.length) {
    return 0;
  }

  offlineEventQueue.delete(userId);
  const now = Date.now();
  let delivered = 0;
  queue.forEach((event) => {
    if (now - event.queuedAt > QUEUED_EVENT_TTL_MS) {
      return;
    }
    const message = JSON.stringify({ type: event.type, payload: event.payload });
    presence.getSocketIds(userId).forEach((socketId) => {
      const socket = socketRegistry.get(socketId);
      if (socket?.readyState === 1) {
        socket.send(message);
        delivered += 1;
      }
    });
  });
  return delivered;
}

export async function addConnection(userId, socket) {
  return presence.addConnection(userId, socket);
}

export async function removeConnection(socket) {
  return presence.removeConnection(socket);
}

export async function updateStatus(userId, status) {
  return presence.updateStatus(userId, status);
}

export async function getOnlineFriends(userId) {
  return presence.getOnlineFriends(userId);
}

export function getStatus(userId) {
  return presence.getStatus(userId);
}

export function startHeartbeat(
  wss,
  intervalMs = HEARTBEAT_INTERVAL_MS,
  timeoutMs = HEARTBEAT_TIMEOUT_MS
) {
  const interval = setInterval(() => {
    const now = Date.now();
    wss.clients.forEach((socket) => {
      if (now - socket.klyvochatLastPongAt >= timeoutMs) {
        socket.terminate();
        return;
      }
      try {
        socket.ping();
      } catch {
        socket.terminate();
      }
    });
  }, intervalMs);

  interval.unref?.();
  wss.on('close', () => clearInterval(interval));
  return interval;
}

export { connectionsByUser, presence, statusByUser };
