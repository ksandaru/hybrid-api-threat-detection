# Phase 6 — Resume Notes for Claude Code

Status: **Not started.** Hard dependency on Phase 3 (rule engine +
orchestrator skeleton) and Phase 5 (running FastAPI `/predict` endpoint).

## Facts to reuse from earlier phases

- `.env.example` already defines `ML_SERVICE_URL` and
  `DETECTION_THRESHOLD` — reuse these exact variable names.
- Fail-open is a deliberate, spec-mandated design choice (not a bug) —
  document it clearly in this phase's `IMPLEMENTATION.md` since it's a
  discussion point for the dissertation (availability vs. security
  trade-off).

## When this phase is done

Fill in `IMPLEMENTATION.md`, `MEMORY.md`, `FILES.md`, update status here.
