import express from 'express';
import { authMiddleware } from '../middleware/auth.js';
import { getPool } from '../database/db.js';
import {
  getFriends,
  getPendingFriendRequests,
  getUserById,
} from '../websocket/friend-service.js';

const router = express.Router();

router.get('/me', authMiddleware, async (req, res) => {
  try {
    const pool = getPool();
    const [rows] = await pool.execute(
      'SELECT id, username, email FROM users WHERE id = ?',
      [req.user.userId]
    );

    if (rows.length === 0) {
      return res.status(404).json({ error: 'User not found' });
    }

    res.json(rows[0]);
  } catch (err) {
    console.error('Get me error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/friends', authMiddleware, async (req, res) => {
  try {
    const friends = await getFriends(req.user.userId);
    res.json({ friends });
  } catch (err) {
    console.error('Get friends error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/friend-requests', authMiddleware, async (req, res) => {
  try {
    const requests = await getPendingFriendRequests(req.user.userId);
    res.json({ requests });
  } catch (err) {
    console.error('Get friend requests error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/profile/:userId', authMiddleware, async (req, res) => {
  try {
    const user = await getUserById(req.params.userId);
    if (!user) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json(user);
  } catch (err) {
    console.error('Get profile error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.get('/search', authMiddleware, async (req, res) => {
  try {
    const { q } = req.query;
    if (!q) {
      return res.status(400).json({ error: 'Query required' });
    }

    const pool = getPool();
    const [rows] = await pool.execute(
      'SELECT id, username, email FROM users WHERE email LIKE ? OR username LIKE ? LIMIT 50',
      [`%${q}%`, `%${q}%`]
    );

    res.json(rows);
  } catch (err) {
    console.error('Search error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

export default router;
