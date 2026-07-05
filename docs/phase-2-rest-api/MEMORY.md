# Phase 2 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **In-memory user store, not Postgres, for auth.** The spec allows either.
  In-memory means Phase 2 is fully testable standalone, without waiting for
  Phase 7's Postgres container — important since Phase 8's attack
  simulation traffic targets `/api/auth/login` directly and shouldn't be
  blocked on Docker Compose being finished.
- **`/api/auth/login` returns 401 for both "unknown user" and "wrong
  password", never 404 for the former.** Distinguishing them would let an
  attacker enumerate valid usernames trivially, which directly undermines
  the credential-stuffing detection scenario this project is built around.
- **`/api/search/vulnerable` never executes its constructed query
  string.** It's returned in the response body so the detection pipeline
  and attack-sim scripts have something realistic to inspect, but nothing
  is ever run against a real database — this keeps the endpoint faithful
  to "receives attack payloads" without violating the project's own ethics
  constraint against real exploitable targets.
- **`logRequest()` in `api/db/pool.js` swallows its own errors.** Postgres
  isn't provisioned until Phase 7, so every call to `logRequest()` between
  now and then would otherwise throw and potentially break the request
  path it's supposed to be silently observing. `console.error` and move on.

## Gotcha encountered

- **No `request_log` table exists anywhere yet.** `db/pool.js`'s
  `logRequest()` assumes a `request_log` table with columns
  `(method, path, ip, features, decision, created_at)`, but there is no
  migration or init-SQL file in the spec's directory structure that
  creates it. This needs to be added in Phase 7, most likely as an init
  script mounted into the `db` Postgres container
  (`docker-entrypoint-initdb.d/`). Flagging here so it isn't forgotten —
  see `docs/phase-7-docker-compose/AI_CONTEXT.md`.

## Process note

- Tested the phase's deliverable check by actually starting the server
  (`node server.js`) and running real `curl` requests, rather than only
  reading the code — caught nothing wrong this time, but this is the
  standard to keep applying, especially once Phase 3's detection
  middleware adds a rule-based blocking path that's easy to get wrong in
  ways that only show up at runtime.
