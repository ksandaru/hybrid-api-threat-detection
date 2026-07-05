# Phase 2 — AI Context

## Original spec goal

> A working Node.js/Express API with endpoints that can be attacked,
> running in Docker.

## Tasks (as written)

1. `api/server.js`: Express app, JSON body parsing, `helmet`, `morgan`
   logging, `/health` route.
2. `api/routes/auth.js`: `POST /api/auth/register` and
   `POST /api/auth/login`. In-memory or Postgres user store, `bcryptjs`
   password hashing, `jsonwebtoken` on success. Return `401` on bad
   credentials. (Brute-force / credential-stuffing target.)
3. `api/routes/search.js`: `GET /api/search/vulnerable?q=` (simulate
   SQLi-vulnerable query — doesn't need a real exploitable DB, just needs
   to receive attack payloads) and `GET /api/search/secure?q=`
   (parameterised/safe version for comparison).
4. `api/routes/orders.js`: `GET /api/orders/:id` — generic JWT-protected
   resource.
5. `api/db/pool.js`: PostgreSQL pool + a `logRequest()` helper (method,
   path, ip, features, decision, timestamp).
6. `api/test/endpoints.http`: sample requests (normal login, SQLi search,
   etc.).

## Deliverable check (as written)

`curl` normal login → 200; wrong password → 401;
`/api/search/vulnerable?q=laptop` → 200. All endpoints reachable.

## Suggested commit message (as written)

`feat: express REST API with vulnerable and secure endpoints`

## Status

**Not started.** Stub files exist from Phase 0 scaffolding only.
