# Phase 8 — Resume Notes for Claude Code

Status: **Complete.**

## Facts to reuse

- **Run flags:** the harness needs `TRUST_PROXY=1` (distinct client sources) and
  `DETECTION_TRACE=1` (per-request scores in response headers). Start the stack
  with both, or the numbers are wrong in ways that look plausible.
- **The ML term is scoped to `/api/search` via `config.mlPayloadPaths`.** Auth
  and orders are rule-only. This is the Phase 8 fix for the Phase 6 blocker; do
  not "restore" ML on auth without re-reading why it was removed.
- **The endpoint check matches `req.originalUrl`, not `req.path`.** The
  middleware is mounted at `/api`, so `req.path` has that prefix stripped.
- **Traffic CSVs are gitignored and regenerate from fixed seeds.** The committed
  artefact is `evaluation/threshold_recalibration.md`.

## For Phase 9

- Decide 0.7 vs 0.8 threshold across all four configurations, rather than
  setting it here.
- Each client has a distinct source, but one machine is still not a load test.

## Ethics constraint (do not violate)

Credential-stuffing pairs must be **synthetic**, generated for this
project — never real leaked-credential lists, even if publicly circulated
ones would be "realistic." All traffic targets only this project's own
local API.

## When this phase is done

Fill in `IMPLEMENTATION.md`, `MEMORY.md`, `FILES.md`, update status here.
