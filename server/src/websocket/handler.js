import { wsAuthenticate } from '../middleware/auth.js';
import { getPool } from '../database/db.js';
import {
  acceptFriendRequest,
  getFriends,
  getPendingFriendRequests,
  rejectFriendRequest,
  removeFriend,
  sendFriendRequest,
  FriendServiceError,
} from './friend-service.js';
import {
  drainQueuedEvents,
  getStatus,
  presence,
  registerSocket,
  removeConnection,
  sendToUser,
  unregisterSocket,
  updateStatus,
} from './presence.js';
import { handleSignaling } from './signaling.js';

const AUTH_TIMEOUT_MS = 10_000;

function sendJson(socket, type, payload = {}) {
  if (socket.readyState !== 1) {
    return false;
  }
  socket.send(JSON.stringify({ type, payload }));
  return true;
}

async function getUser(userId) {
  const pool = getPool();
  const [rows] = await pool.execute(
    'SELECT id, username, email, created_at FROM users WHERE id = ?',
    [userId]
  );
  return rows[0] || null;
}

async function authenticateSocket(socket, token) {
  if (!token || socket.klyvochatUserId) {
    throw new Error('Socket is already authenticated or token is missing');
  }

  const decoded = wsAuthenticate(token);
  if (!decoded?.userId) {
    throw new Error('Invalid token');
  }

  const user = await getUser(decoded.userId);
  if (!user) {
    throw new Error('User not found');
  }

  socket.klyvochatUserId = user.id;
  socket.klyvochatLastPongAt = Date.now();
  registerSocket(socket);
  await import('./presence.js').then(({ presence }) => presence.addConnection(user.id, socket));

  const [friends, pendingRequests] = await Promise.all([
    getFriends(user.id),
    getPendingFriendRequests(user.id),
  ]);
  drainQueuedEvents(user.id);

  const friendsWithPresence = friends.map((friend) => ({
    ...friend,
    status: getStatus(friend.friend_id) || 'offline',
  }));

  sendJson(socket, 'auth_ok', {
    user_id: user.id,
    user,
    friends: friendsWithPresence,
    pending_requests: pendingRequests,
  });
  return user;
}

async function handleStatus(socket, message) {
  const payload = message.payload || {};
  const status = message.status || payload.status || payload;
  const { updateStatus } = await import('./presence.js');
  await updateStatus(socket.klyvochatUserId, status);
  sendJson(socket, 'status_updated', { status });
}

function friendActionFromMessage(message) {
  if (message.type === 'friend_action') {
    return {
      action: message.action || message.payload?.action,
      payload: message.payload || {},
    };
  }

  const actions = {
    friend_request: 'request',
    friend_accept: 'accept',
    friend_reject: 'reject',
    friend_remove: 'remove',
  };
  if (actions[message.type]) {
    return { action: actions[message.type], payload: message.payload || {} };
  }
  return {};
}

async function handleFriendAction(socket, message) {
  const { action, payload } = friendActionFromMessage(message);
  const userId = socket.klyvochatUserId;

  if (action === 'request' || action === 'send_request') {
    const email = payload.email || payload.target_email;
    if (!email) {
      throw new Error('Email is required');
    }
    const result = await sendFriendRequest(userId, email);
    if (result.created) {
      const requester = await getUser(result.request.requester_id);
      sendToUser(
        result.request.addressee_id,
        'friend_request',
        {
          ...result.request,
          user: requester || result.request.user,
        }
      );
    }
    sendJson(socket, 'friend_action_result', {
      action: 'request',
      ok: true,
      request: result.request,
      created: result.created,
    });
    return;
  }

  if (action === 'accept' || action === 'accept_request') {
    const requestId = payload.request_id || payload.id;
    if (!requestId) {
      throw new Error('request_id is required');
    }
    const result = await acceptFriendRequest(userId, requestId);
    if (result.friend) {
      const currentUser = await getUser(userId);
      sendToUser(result.friend.id, 'friend_accept', {
        friend: currentUser || result.friend,
        request: result.request,
      });
      sendJson(socket, 'friend_accept', {
        friend: result.friend,
        request: result.request,
      });
    }
    sendJson(socket, 'friend_action_result', {
      action: 'accept',
      ok: true,
      ...result,
    });
    return;
  }

  if (action === 'reject' || action === 'reject_request') {
    const requestId = payload.request_id || payload.id;
    if (!requestId) {
      throw new Error('request_id is required');
    }
    const result = await rejectFriendRequest(userId, requestId);
    sendToUser(result.requester_id, 'friend_reject', result);
    sendJson(socket, 'friend_action_result', {
      action: 'reject',
      ok: true,
      request: result,
    });
    return;
  }

  if (action === 'remove' || action === 'remove_friend') {
    const friendId = payload.friend_id || payload.user_id || payload.id;
    if (!friendId) {
      throw new Error('friend_id is required');
    }
    const removed = await removeFriend(userId, friendId);
    sendToUser(friendId, 'friend_remove', { friend_id: friendId, user_id: userId });
    sendJson(socket, 'friend_action_result', {
      action: 'remove',
      ok: removed,
      friend_id: friendId,
    });
    return;
  }

  throw new Error('Unknown friend action');
}

export async function handleMessage(socket, rawData) {
  let message;
  try {
    message = JSON.parse(rawData.toString());
  } catch {
    sendJson(socket, 'error', { code: 'invalid_json', message: 'Invalid JSON' });
    return;
  }

  if (!message || typeof message.type !== 'string') {
    sendJson(socket, 'error', { code: 'invalid_message', message: 'Message type is required' });
    return;
  }

  if (message.type === 'auth') {
    await authenticateSocket(socket, message.token || message.payload?.token);
    return;
  }

  if (!socket.klyvochatUserId) {
    sendJson(socket, 'error', { code: 'not_authenticated', message: 'Authenticate first' });
    return;
  }

  try {
    switch (message.type) {
      case 'status':
      case 'status_update':
        await handleStatus(socket, message);
        break;
      case 'signaling':
        await handleSignaling(socket.klyvochatUserId, message);
        break;
      case 'friend_action':
      case 'friend_request':
      case 'friend_accept':
      case 'friend_reject':
      case 'friend_remove':
        await handleFriendAction(socket, message);
        break;
      case 'ping':
        sendJson(socket, 'pong', {});
        break;
      default:
        sendJson(socket, 'error', {
          code: 'unknown_message',
          message: `Unknown message type: ${message.type}`,
        });
    }
  } catch (err) {
    const code = err instanceof FriendServiceError ? err.code : 'action_failed';
    sendJson(socket, 'error', { code, message: err.message || 'Request failed' });
  }
}

export function handleWebSocketConnection(socket) {
  socket.klyvochatLastPongAt = Date.now();
  socket.klyvochatUserId = null;
  socket.klyvochatAuthTimer = setTimeout(() => {
    if (!socket.klyvochatUserId && socket.readyState === 1) {
      socket.terminate();
    }
  }, AUTH_TIMEOUT_MS);
  socket.klyvochatAuthTimer.unref?.();

  socket.on('pong', () => {
    socket.klyvochatLastPongAt = Date.now();
  });

  socket.on('message', (rawData) => {
    socket.klyvochatMessageChain = (socket.klyvochatMessageChain || Promise.resolve())
      .then(() => handleMessage(socket, rawData))
      .catch((err) => {
        sendJson(socket, 'error', {
          code: 'action_failed',
          message: err.message || 'Request failed',
        });
      });
  });

  socket.on('close', () => {
    clearTimeout(socket.klyvochatAuthTimer);
    unregisterSocket(socket);
    removeConnection(socket).catch((err) => {
      console.error('Failed to remove WebSocket presence:', err);
    });
  });

  socket.on('error', (err) => {
    console.error('WebSocket error:', err.message);
  });
}

export { AUTH_TIMEOUT_MS, authenticateSocket, sendJson };
