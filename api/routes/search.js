const express = require('express');

const router = express.Router();

const PRODUCTS = [
  { id: 1, name: 'laptop', price: 999 },
  { id: 2, name: 'mouse', price: 25 },
  { id: 3, name: 'keyboard', price: 45 },
  { id: 4, name: 'monitor', price: 199 },
];

router.get('/vulnerable', (req, res) => {
  const q = req.query.q || '';
  const simulatedQuery = `SELECT * FROM products WHERE name LIKE '%${q}%'`;
  const results = PRODUCTS.filter((p) => p.name.includes(String(q).toLowerCase()));
  return res.status(200).json({ query: simulatedQuery, results });
});

// GET /api/search/secure?q=
// Safe equivalent: no string built from user input is ever treated as a
// query, filtering happens purely in application code.
router.get('/secure', (req, res) => {
  const q = String(req.query.q || '').toLowerCase();
  const results = PRODUCTS.filter((p) => p.name.includes(q));
  return res.status(200).json({ results });
});

module.exports = router;
