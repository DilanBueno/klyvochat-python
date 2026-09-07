import express from 'express';
import bcrypt from 'bcrypt';
import jwt from 'jsonwebtoken';
import { config } from '../config.js';

const router = express.Router();

const users = new Map();

router.post('/register', async (req, res) => {
  try {
    const { username, email, password } = req.body;
    
    if (!username || !email || !password) {
      return res.status(400).json({ error: 'Missing required fields' });
    }
    
    if (users.has(email)) {
      return res.status(409).json({ error: 'User already exists' });
    }
    
    const passwordHash = await bcrypt.hash(password, 10);
    const user = {
      id: crypto.randomUUID(),
      username,
      email,
      passwordHash,
      publicKey: null,
      createdAt: new Date(),
    };
    
    users.set(email, user);
    
    const token = jwt.sign({ userId: user.id, email }, config.jwtSecret, {
      expiresIn: config.jwtExpiresIn,
    });
    const refreshToken = jwt.sign({ userId: user.id }, config.jwtSecret, {
      expiresIn: config.refreshExpiresIn,
    });
    
    res.json({
      token,
      refreshToken,
      user: { id: user.id, username, email },
    });
  } catch (err) {
    console.error('Register error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    const user = users.get(email);
    if (!user) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const valid = await bcrypt.compare(password, user.passwordHash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }
    
    const token = jwt.sign({ userId: user.id, email }, config.jwtSecret, {
      expiresIn: config.jwtExpiresIn,
    });
    const refreshToken = jwt.sign({ userId: user.id }, config.jwtSecret, {
      expiresIn: config.refreshExpiresIn,
    });
    
    res.json({
      token,
      refreshToken,
      user: { id: user.id, username: user.username, email },
    });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Internal server error' });
  }
});

router.post('/refresh', (req, res) => {
  try {
    const { refreshToken } = req.body;
    
    const decoded = jwt.verify(refreshToken, config.jwtSecret);
    const token = jwt.sign({ userId: decoded.userId }, config.jwtSecret, {
      expiresIn: config.jwtExpiresIn,
    });
    
    res.json({ token });
  } catch (err) {
    res.status(401).json({ error: 'Invalid refresh token' });
  }
});

export default router;
