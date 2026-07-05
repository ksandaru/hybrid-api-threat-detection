# Phase 7 — Resume Notes for Claude Code

Status: **Not started.** Depends on Phases 2-6 (api and ml services having
real, runnable code — not just stubs).

## Facts to reuse from earlier phases

- `api/Dockerfile` and `ml/Dockerfile` already exist from Phase 0
  (node:22-slim, python:3.13-slim) — reuse them, don't recreate.
- `.env.example` already lists `DATABASE_URL` with the expected
  `detector`/`detector123`/`api_threat_detection` convention for the `db`
  service credentials.

## When this phase is done

Fill in `IMPLEMENTATION.md`, `MEMORY.md`, `FILES.md`, update status here.
