# Phase 3 — AI Context

## Original spec goal

> Express middleware that extracts features and blocks obvious attacks with
> rules — BEFORE any ML exists. This is the fast path and also baseline #1.

## Tasks (as written)

1. `api/middleware/featureExtractor.js`: implement the SAME feature list as
   `ml/features.py` (Phase 1 §4.4). Maintain per-IP sliding-window state (in
   memory is fine for a single-node dissertation; document this
   limitation) for flow-level features.
2. `api/middleware/ruleEngine.js`: fast checks — high `sql_keyword_count`,
   presence of `--`/`OR 1=1`, `requests_per_min_ip` over threshold,
   `login_failure_ratio` over threshold. Return
   `{ blocked, alerts[], ruleScore }`.
3. `api/middleware/detection.js`: orchestrator. Extract features → run
   rules → if a high-severity rule fires, block with `403`. Otherwise (for
   now) call `next()`. Log everything via `db/pool.js`.
4. Wire `app.use('/api', detectionMiddleware)` in `server.js` before
   routes.

## Deliverable check (as written)

SQLi payload to `/api/search/vulnerable` is blocked by rules (403). Rapid
repeated `/api/auth/login` failures trip the rate rule. Normal traffic
passes.

## Suggested commit message (as written)

`feat: detection middleware with rule-based fast path`

## Status

**Not started.**
