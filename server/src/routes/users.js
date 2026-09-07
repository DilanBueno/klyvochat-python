import express from 'express';
import jwt from 'jsonwebtoken';
import { config } from '../config.js';

const router = express.Router();

const users = new Map();

function authenticate(req, res, next) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }
  
  const token = authHeader.slice(7);
  try {
    const decoded = jwt.verify(token, config.jwtSecret);
    req.user = decoded;
    next();
  } catch {
    res.status(401).json({ error: 'Invalid token' });
  }
}

router.get('/me', authenticate, (req, res) => {
  const user = users.get(req.user.email);
  if (!user) {
    return res.status(404).json({ error: 'User not found' });
  }
  res.json({ id: user.id, username: user.username, email: user.email });
});

router.get('/search', authenticate, (req, res) => {
  const { q } = req.query;
  if (!q) {
    return res.status(400).json({ error: 'Query required' });
  }
  
  const results = [];
  for (const user of users.values()) {
    if (user.email.includes(q) || user.username.toLowerCase().includes(q.toLowerCase())) {
      results.push({ id: user.id, username: user.username, email: user.email });
    }
  }
  res.json(results);
});

export default router;
