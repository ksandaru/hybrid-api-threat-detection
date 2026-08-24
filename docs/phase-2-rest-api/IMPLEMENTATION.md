# Phase 2 — Implementation Log

Status: **Complete.**

### Step 1 — Config module

- **What:** `api/config/index.js` loads `.env` via `dotenv` and exports a
  single config object (`port`, `mlServiceUrl`, `databaseUrl`,
  `detectionThreshold`, `jwtSecret`) with sane fallback defaults.
- **Why:** Every later phase (middleware, DB pool, ML client) needs the
  same env-driven values — centralising them in one module avoids each
  file reading `process.env` directly with its own inconsistent defaults.
- **How:** Plain `require('dotenv').config()` at the top, then a `module.exports`
  object with `parseInt`/`parseFloat` coercion for the numeric env vars
  (`PORT`, `DETECTION_THRESHOLD`), since `process.env` values are always
  strings.

### Step 2 — Database pool and request logging

- **What:** `api/db/pool.js` creates a `pg.Pool` from `DATABASE_URL` and
  exports a `logRequest()` helper that inserts into a `request_log` table.
- **Why:** The spec wants every request's method/path/ip/features/decision
  logged for later analysis (Phase 9 evaluation), but Postgres itself isn't
  provisioned until Phase 7's docker-compose stack exists.
- **How:** `logRequest()` wraps its query in `try/catch` and only
  `console.error`s on failure rather than throwing — so calling it before
  Postgres exists (all of Phase 2 through Phase 6) never crashes the
  request path. **Note for Phase 7:** the `request_log` table itself
  doesn't exist yet anywhere — Phase 7 needs either an init SQL script
  mounted into the `db` service, or a small migration step, before
  `logRequest()` will actually persist anything instead of just logging a
  connection error.

### Step 3 — Auth routes (brute-force / credential-stuffing target)

- **What:** `api/routes/auth.js` — `POST /api/auth/register` and
  `POST /api/auth/login`, backed by an in-memory `Map` (not Postgres).
- **Why:** The spec explicitly allows "in-memory or Postgres user store" —
  in-memory was chosen to keep Phase 2 fully testable without waiting for
  Phase 7's Postgres container, since auth is exactly the surface Phase 8's
  brute-force/credential-stuffing traffic generators will target and
  needs to work standalone.
- **How:** `bcryptjs` hashes passwords on register (`bcrypt.hash(password, 10)`);
  login compares with `bcrypt.compare` and signs a `jsonwebtoken` (1 hour
  expiry) on success. Returns `401` uniformly for "user doesn't exist" and
  "wrong password" (not `404` for the former) — deliberately, so login
  responses don't leak which usernames exist, which would otherwise make
  credential-stuffing trivially easier to optimise against.

### Step 4 — Search routes (SQLi target)

- **What:** `api/routes/search.js` — `GET /api/search/vulnerable?q=` and
  `GET /api/search/secure?q=`, both backed by a small hardcoded product
  list (no real database).
- **Why:** Per the spec, the vulnerable endpoint "does not need a real
  exploitable DB, it just needs to receive attack payloads" — the ethics
  constraint (no real vulnerable targets) is satisfied by never executing
  the constructed query string against anything, while still giving the
  detection pipeline and attack-sim traffic (Phase 8) a realistic surface
  to send SQLi payloads at.
- **How:** `/vulnerable` builds the query string via naive template-literal
  concatenation (`` `SELECT * FROM products WHERE name LIKE '%${q}%'` ``)
  and returns it in the response body alongside a best-effort
  `.filter()` match — this exposes exactly what an unsanitised
  implementation would send to a real database, for feature
  extraction/attack-sim purposes, without ever running it. `/secure` never
  builds a query string at all — it filters the same in-memory list
  directly in application code, which is what a parameterised-query
  implementation is functionally equivalent to.

### Step 5 — Protected resource route

- **What:** `api/routes/orders.js` — `GET /api/orders/:id`, guarded by an
  inline `requireAuth` middleware checking `Authorization: Bearer <token>`.
- **Why:** Spec asks for "a generic JWT-protected resource" to demonstrate
  the auth token issued by `/login` actually protects something.
- **How:** `requireAuth` splits the `Authorization` header, verifies with
  `jsonwebtoken.verify(token, config.jwtSecret)`, returns `401` on any
  missing/malformed/invalid/expired token (caught via `try/catch` around
  `verify`), otherwise attaches the decoded payload to `req.user` and
  calls `next()`.

### Step 6 — Server bootstrap

- **What:** `api/server.js` — Express app with `helmet()`, `morgan('dev')`,
  `express.json()`, a `GET /health` route, and the three route modules
  mounted at `/api/auth`, `/api/search`, `/api/orders`.
- **Why:** Matches the spec's Phase 2 task list exactly. `require.main === module`
  guards `app.listen()` so the same file can be `require()`d by a future
  test suite without starting a real server.
- **How:** Left an explicit `// TODO (Phase 3)` comment marking exactly
  where `app.use('/api', detectionMiddleware)` needs to go (before the
  route mounts) — a placeholder rather than silently forgetting the wiring
  point.

### Step 7 — Manual verification against the spec's deliverable check

- **What:** Ran `npm install` in `api/`, started the server with a copy of
  `.env.example` as `.env`, and used `curl` to exercise every endpoint.
- **Why:** The spec's deliverable check for this phase is explicit ("curl
  normal login → 200; wrong password → 401;
  `/api/search/vulnerable?q=laptop` → 200. All endpoints reachable.") —
  verified directly rather than assumed from reading the code.
- **How:** Results, all as expected:
  - `GET /health` → 200
  - `POST /api/auth/register` (alice) → 201 (returned as part of testing;
    the spec doesn't require a specific status for register, 201 was
    chosen as the correct REST convention for resource creation)
  - `POST /api/auth/login` correct password → 200 + JWT
  - `POST /api/auth/login` wrong password → 401
  - `GET /api/search/vulnerable?q=laptop` → 200, correct match
  - `GET /api/search/vulnerable?q=' OR '1'='1` → 200, no crash, query
    string reflects the raw payload as expected
  - `GET /api/search/secure?q=mouse` → 200, correct match
  - `GET /api/orders/123` no token → 401
  - `GET /api/orders/123` garbage token → 401
  - `GET /api/orders/123` valid token → 200, `owner` field correctly
    decoded from the JWT
  - Server and temporary `.env` cleaned up afterward (`.env` is gitignored
    and was only created locally for this manual test, then removed).
