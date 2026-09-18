import { randomUUID } from 'crypto';
import { getPool } from '../database/db.js';

class FriendServiceError extends Error {
  constructor(code, message, statusCode = 400) {
    super(message);
    this.code = code;
    this.statusCode = statusCode;
  }
}

function requestFromRow(row) {
  return {
    id: row.id,
    requester_id: row.requester_id,
    addressee_id: row.addressee_id,
    status: row.status,
    created_at: row.created_at,
    updated_at: row.updated_at,
    direction: row.direction,
    user: row.user_id
      ? {
          id: row.user_id,
          username: row.username,
          email: row.email,
        }
      : undefined,
  };
}

function friendFromRow(row) {
  return {
    id: row.friend_id,
    user_id: row.friend_id,
    username: row.username,
    name: row.username,
    email: row.email,
    status: 'offline',
    added_at: row.added_at || row.created_at,
  };
}

export async function getFriends(userId) {
  const pool = getPool();
  const [rows] = await pool.query(
    `
      SELECT f.id, f.addressee_id AS friend_id, u.username, u.email,
             f.created_at AS added_at
      FROM friendships f
      JOIN users u ON u.id = f.addressee_id
      WHERE f.requester_id = ? AND f.status = 'accepted'
      UNION
      SELECT f.id, f.requester_id AS friend_id, u.username, u.email,
             f.created_at AS added_at
      FROM friendships f
      JOIN users u ON u.id = f.requester_id
      WHERE f.addressee_id = ? AND f.status = 'accepted'
      ORDER BY username
    `,
    [userId, userId]
  );
  return rows.map(friendFromRow);
}

export async function getPendingFriendRequests(userId) {
  const pool = getPool();
  const [rows] = await pool.query(
    `
      SELECT fr.id, fr.requester_id, fr.addressee_id, fr.status,
             fr.created_at, fr.updated_at, 'incoming' AS direction,
             u.id AS user_id, u.username, u.email
      FROM friend_requests fr
      JOIN users u ON u.id = fr.requester_id
      WHERE fr.addressee_id = ? AND fr.status = 'pending'
      UNION
      SELECT fr.id, fr.requester_id, fr.addressee_id, fr.status,
             fr.created_at, fr.updated_at, 'outgoing' AS direction,
             u.id AS user_id, u.username, u.email
      FROM friend_requests fr
      JOIN users u ON u.id = fr.addressee_id
      WHERE fr.requester_id = ? AND fr.status = 'pending'
      ORDER BY created_at
    `,
    [userId, userId]
  );
  return rows.map(requestFromRow);
}

export async function getUserById(userId) {
  const pool = getPool();
  const [rows] = await pool.execute(
    'SELECT id, username, email, created_at FROM users WHERE id = ?',
    [userId]
  );
  return rows[0] || null;
}

export async function getUserByEmail(email) {
  const normalizedEmail = email.trim().toLowerCase();
  const pool = getPool();
  const [rows] = await pool.execute(
    'SELECT id, username, email FROM users WHERE LOWER(email) = ?',
    [normalizedEmail]
  );
  return rows[0] || null;
}

export async function sendFriendRequest(requesterId, email) {
  const target = await getUserByEmail(email);
  if (!target) {
    throw new FriendServiceError('user_not_found', 'Usuário não encontrado', 404);
  }
  if (target.id === requesterId) {
    throw new FriendServiceError('cannot_add_self', 'Você não pode adicionar a si mesmo');
  }

  const pool = getPool();
  const connection = await pool.getConnection();
  try {
    await connection.beginTransaction();
    const [existingRows] = await connection.execute(
      `
        SELECT id, requester_id, addressee_id, status, created_at, updated_at
        FROM friend_requests
        WHERE status IN ('pending', 'accepted')
          AND ((requester_id = ? AND addressee_id = ?)
            OR (requester_id = ? AND addressee_id = ?))
        LIMIT 1
      `,
      [requesterId, target.id, target.id, requesterId]
    );

    if (existingRows.length > 0) {
      const existing = requestFromRow(existingRows[0]);
      if (existing.status === 'accepted') {
        await connection.execute(
          `
            INSERT INTO friendships
              (id, requester_id, addressee_id, status, created_at, updated_at)
            VALUES (?, ?, ?, 'accepted', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
              status = 'accepted',
              updated_at = CURRENT_TIMESTAMP
          `,
          [existing.id, existing.requester_id, existing.addressee_id]
        );
      }
      await connection.commit();
      existing.user = target;
      return { request: existing, created: false };
    }

    const requestId = randomUUID();
    await connection.execute(
      `
        INSERT INTO friend_requests
          (id, requester_id, addressee_id, status, created_at, updated_at)
        VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
      `,
      [requestId, requesterId, target.id]
    );
    const [rows] = await connection.execute(
      `
        SELECT id, requester_id, addressee_id, status, created_at, updated_at
        FROM friend_requests WHERE id = ?
      `,
      [requestId]
    );
    await connection.commit();
    const request = requestFromRow(rows[0]);
    request.user = target;
    return { request, created: true };
  } catch (err) {
    await connection.rollback();
    throw err;
  } finally {
    connection.release();
  }
}

export async function acceptFriendRequest(userId, requestId) {
  const pool = getPool();
  const connection = await pool.getConnection();
  try {
    await connection.beginTransaction();
    const [rows] = await connection.execute(
      `
        SELECT id, requester_id, addressee_id, status, created_at, updated_at
        FROM friend_requests
        WHERE id = ? AND addressee_id = ? AND status = 'pending'
        LIMIT 1
      `,
      [requestId, userId]
    );
    if (rows.length === 0) {
      throw new FriendServiceError(
        'request_not_found',
        'Pedido de amizade não encontrado',
        404
      );
    }

    await connection.execute(
      `
        UPDATE friend_requests
        SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
      `,
      [requestId]
    );
    await connection.execute(
      `
        INSERT INTO friendships
          (id, requester_id, addressee_id, status, created_at, updated_at)
        VALUES (?, ?, ?, 'accepted', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
          status = 'accepted',
          updated_at = CURRENT_TIMESTAMP
      `,
      [rows[0].id, rows[0].requester_id, rows[0].addressee_id]
    );
    await connection.commit();

    const requester = await getUserById(rows[0].requester_id);
    return {
      request: {
        ...rows[0],
        status: 'accepted',
      },
      friend: requester
        ? {
            id: requester.id,
            user_id: requester.id,
            username: requester.username,
            name: requester.username,
            email: requester.email,
            status: 'offline',
          }
        : null,
    };
  } catch (err) {
    await connection.rollback();
    throw err;
  } finally {
    connection.release();
  }
}

export async function rejectFriendRequest(userId, requestId) {
  const pool = getPool();
  const [requestRows] = await pool.execute(
    `
      SELECT requester_id FROM friend_requests
      WHERE id = ? AND addressee_id = ? AND status = 'pending'
      LIMIT 1
    `,
    [requestId, userId]
  );
  if (requestRows.length === 0) {
    throw new FriendServiceError(
      'request_not_found',
      'Pedido de amizade não encontrado',
      404
    );
  }

  const [result] = await pool.execute(
    `
      UPDATE friend_requests
      SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
      WHERE id = ? AND addressee_id = ? AND status = 'pending'
    `,
    [requestId, userId]
  );
  return { id: requestId, requester_id: requestRows[0].requester_id, status: 'rejected' };
}

export async function removeFriend(userId, friendId) {
  const pool = getPool();
  const connection = await pool.getConnection();
  try {
    await connection.beginTransaction();
    const [requestResult] = await connection.execute(
      `
        DELETE FROM friend_requests
        WHERE status = 'accepted'
          AND ((requester_id = ? AND addressee_id = ?)
            OR (requester_id = ? AND addressee_id = ?))
      `,
      [userId, friendId, friendId, userId]
    );
    const [friendshipResult] = await connection.execute(
      `
        DELETE FROM friendships
        WHERE (requester_id = ? AND addressee_id = ?)
           OR (requester_id = ? AND addressee_id = ?)
      `,
      [userId, friendId, friendId, userId]
    );
    await connection.commit();
    return requestResult.affectedRows > 0 || friendshipResult.affectedRows > 0;
  } catch (err) {
    await connection.rollback();
    throw err;
  } finally {
    connection.release();
  }
}

export async function getFriendIds(userId) {
  const pool = getPool();
  const [rows] = await pool.query(
    `
      SELECT addressee_id AS user_id FROM friendships
      WHERE requester_id = ? AND status = 'accepted'
      UNION
      SELECT requester_id AS user_id FROM friendships
      WHERE addressee_id = ? AND status = 'accepted'
    `,
    [userId, userId]
  );
  return rows.map((row) => row.user_id);
}

export async function areFriends(userId, otherUserId) {
  const pool = getPool();
  const [rows] = await pool.execute(
    `
      SELECT 1 AS connected FROM friendships
      WHERE status = 'accepted'
        AND ((requester_id = ? AND addressee_id = ?)
          OR (requester_id = ? AND addressee_id = ?))
      LIMIT 1
    `,
    [userId, otherUserId, otherUserId, userId]
  );
  return rows.length > 0;
}

export { FriendServiceError };
