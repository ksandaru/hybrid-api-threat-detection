const express = require('express');

const router = express.Router();

// Dummy catalogue — no real database backs either endpoint below. The
// point of /vulnerable is to demonstrate the *shape* of a SQLi-vulnerable
// query (unsanitised string concatenation) for the detection pipeline to
// inspect, not to run arbitrary SQL against a live system (see the
// project's ethics constraints: no real exploitable targets).
const PRODUCTS = [
  { id: 1, name: 'laptop', price: 999 },
  { id: 2, name: 'mouse', price: 25 },
  { id: 3, name: 'keyboard', price: 45 },
  { id: 4, name: 'monitor', price: 199 },
];

// GET /api/search/vulnerable?q=
// Simulates a SQLi-vulnerable query by building the raw query string via
// naive concatenation, exactly as an unsafe implementation would. The
// string is never executed against a real database — it's returned so
// the detection middleware/attack-sim traffic has something realistic to
// inspect, per the spec: "it does not need a real exploitable DB, it just
// needs to receive attack payloads."
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
