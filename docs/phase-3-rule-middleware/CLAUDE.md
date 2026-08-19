# Phase 3 — Resume Notes for Claude Code

Status: **Complete.** Rule-only detection is live on every `/api` route and
verified against a running server.

## Facts to reuse

- `api/middleware/featureExtractor.js` mirrors `ml/features.py`. **If you change
  either, change both in the same commit and re-run `node api/test/featureParity.js`.**
  That test is the enforcement mechanism for NFR3, not a formality.
- The SQL keyword list is frozen. It defines the existing corpus; extending it
  invalidates all 677,166 rows of precomputed features. Close detection gaps by
  reweighting rules instead.
- `DETECTION_MODE` already exists (`off`, `rules`, `hybrid`). Phase 9 should
  select baselines with it rather than editing the request path.
- Rule thresholds and the full rule list are exported from `ruleEngine.js` for
  sweeping.
- Two rule-only misses are deliberate and documented: `admin'-- DROP TABLE`
  (scores 0.5, below threshold) and anything depending on keywords outside the
  frozen list. These are the cases the ML stage should demonstrate value on, and
  they are the natural worked example for the Phase 6 deliverable check.

## For Phase 6 (next consumer)

The insertion point is marked in `detection.js` with a `TODO (Phase 6)` comment,
immediately before `combinedScore` is computed. Required behaviour:

- call the inference service only when `detectionMode === 'hybrid'`
- combine `rules.ruleScore` with the ML score, then compare against
  `config.detectionThreshold` — that comparison already exists in `shouldBlock`
- on timeout or error, fall back to the rule verdict and log a warning; never
  block because inference was unavailable

## Traps

- Do not read `req.path` after an async boundary. Express rewrites `req.url`
  during dispatch, so the value differs between entry and the `finish` handler.
  Capture at entry (see Defect 1 in `IMPLEMENTATION.md`).
- Do not record an application outcome for a blocked request; it never reached
  the handler (see Defect 2).
