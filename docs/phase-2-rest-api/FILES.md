# Phase 2 — Files Created / Modified

| File | Purpose |
|---|---|
| `api/config/index.js` | Centralised env-driven config (port, ML service URL, database URL, detection threshold, JWT secret) |
| `api/db/pool.js` | `pg.Pool` + `logRequest()` helper; swallows errors since Postgres doesn't exist until Phase 7 |
| `api/routes/auth.js` | `POST /api/auth/register`, `POST /api/auth/login` — in-memory user store, bcryptjs + jsonwebtoken |
| `api/routes/search.js` | `GET /api/search/vulnerable?q=`, `GET /api/search/secure?q=` — SQLi detection target |
| `api/routes/orders.js` | `GET /api/orders/:id` — JWT-protected resource with inline `requireAuth` middleware |
| `api/server.js` | Express bootstrap — helmet, morgan, JSON body parsing, `/health`, route mounts |
| `api/test/endpoints.http` | Manual REST-client requests covering every endpoint and both success/failure paths |

## Verified but not committed

- `api/node_modules/` — installed via `npm install` (118 packages, 0
  vulnerabilities), gitignored.
- `api/.env` — created temporarily (copied from `.env.example`) to
  manually test the server, then deleted after verification. Not
  committed (gitignored anyway).
