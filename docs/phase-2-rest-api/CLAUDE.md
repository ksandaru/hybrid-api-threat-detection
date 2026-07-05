# Phase 2 — Resume Notes for Claude Code

Status: **Complete.** Server runs standalone (`node server.js` from
`api/`, after `npm install` and a real `.env`), all endpoints manually
verified with curl.

## Facts to reuse from this phase

- Auth is **in-memory**, not Postgres — `users` is a module-level `Map` in
  `api/routes/auth.js`. It resets on every server restart. If Phase 8's
  attack-sim scripts need a persistent/known user to brute-force, register
  it first via `/api/auth/register`, don't assume one exists.
- `api/db/pool.js`'s `logRequest()` silently no-ops (logs to console, not
  the DB) until Phase 7 provisions Postgres **and** something creates the
  `request_log` table — no migration exists yet. Don't be surprised when
  nothing appears in a database during Phase 3-6 testing.
- `requireAuth` in `api/routes/orders.js` is inline, not a shared
  middleware file — if Phase 3/6 need JWT verification elsewhere, either
  import it from `orders.js` or extract it, don't duplicate the
  verify-and-401 logic.
- `/api/search/vulnerable` reflects the raw query string in its JSON
  response (`{ query, results }`) — Phase 3's `featureExtractor.js` should
  read from `req.query.q` directly (the same input), not try to re-parse
  the reflected `query` field.

## When touching this phase again

Update `IMPLEMENTATION.md`/`MEMORY.md`/`FILES.md` here if routes change
materially (e.g. if Phase 6 needs to modify `orders.js` or `auth.js` to
integrate with the detection middleware's blocking behaviour).
