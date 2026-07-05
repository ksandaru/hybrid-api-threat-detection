const express = require('express');
const jwt = require('jsonwebtoken');
const config = require('../config');

const router = express.Router();

function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  const [scheme, token] = header.split(' ');
  if (scheme !== 'Bearer' || !token) {
    return res.status(401).json({ error: 'missing bearer token' });
  }
  try {
    req.user = jwt.verify(token, config.jwtSecret);
    return next();
  } catch (err) {
    return res.status(401).json({ error: 'invalid or expired token' });
  }
}

// GET /api/orders/:id — generic JWT-protected resource, standing in for
// any authenticated endpoint the API might expose.
router.get('/:id', requireAuth, (req, res) => {
  return res.status(200).json({
    id: req.params.id,
    item: 'sample-order',
    status: 'confirmed',
    owner: req.user.sub,
  });
});

module.exports = router;
