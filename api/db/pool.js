const { Pool } = require('pg');
const config = require('../config');

const pool = new Pool({ connectionString: config.databaseUrl });

// Postgres isn't provisioned until Phase 7's docker-compose stack exists.
// Callers should not assume this resolves — logRequest() below swallows
// connection errors so request logging never breaks the request path.
pool.on('error', (err) => {
  console.error('[db] unexpected pool error', err.message);
});

async function logRequest({ method, path, ip, features, decision }) {
  const query = `
    INSERT INTO request_log (method, path, ip, features, decision, created_at)
    VALUES ($1, $2, $3, $4, $5, NOW())
  `;
  try {
    await pool.query(query, [method, path, ip, JSON.stringify(features || {}), decision]);
  } catch (err) {
    console.error('[db] logRequest failed (continuing):', err.message);
  }
}

module.exports = { pool, logRequest };
