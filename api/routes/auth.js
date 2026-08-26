const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const config = require('../config');

const router = express.Router();

const users = new Map();

router.post('/register', async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    return res.status(400).json({ error: 'username and password are required' });
  }
  if (users.has(username)) {
    return res.status(409).json({ error: 'username already exists' });
  }
  const passwordHash = await bcrypt.hash(password, 10);
  users.set(username, { username, passwordHash });
  return res.status(201).json({ username });
});

router.post('/login', async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    return res.status(400).json({ error: 'username and password are required' });
  }
  const user = users.get(username);
  const validPassword = user ? await bcrypt.compare(password, user.passwordHash) : false;
  if (!user || !validPassword) {
    return res.status(401).json({ error: 'invalid credentials' });
  }
  const token = jwt.sign({ sub: username }, config.jwtSecret, { expiresIn: '1h' });
  return res.status(200).json({ token });
});

module.exports = router;
