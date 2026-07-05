# Phase 6 — AI Context

## Original spec goal

> The full hybrid pipeline works end to end.

## Tasks (as written)

1. `api/middleware/mlClient.js`: `axios` POST to `ML_SERVICE_URL/predict`
   with a short timeout (e.g. 200 ms).
2. In `detection.js`: after rules pass, call the ML service. Combine
   `ruleScore` + `mlScore` → if `combined >= DETECTION_THRESHOLD`, block
   `403`; else `next()`.
3. **Fail-open:** if the ML service errors or times out, log a warning and
   fall back to rule-only (do not crash, do not block legitimate traffic).
   Document this design choice for the dissertation.

## Deliverable check (as written)

With ML service up, a subtle attack that rules miss but ML catches is
blocked. With ML service stopped, API still serves traffic (rule-only). No
crashes.

## Suggested commit message (as written)

`feat: integrate hybrid rule+ML detection with fail-open fallback`

## Status

**Not started.**
