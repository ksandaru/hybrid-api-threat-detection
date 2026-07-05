# Phase 2 — Resume Notes for Claude Code

Status: **Not started.** Depends on Phase 0 (done) and Phase 1's
`ml/features.py` existing first is *not* a hard blocker for this phase's
routes/server, but `api/middleware/featureExtractor.js` (Phase 3) does
depend on the feature contract Phase 1 defines — build Phase 2's plain
routes first, detection middleware comes in Phase 3.

## Facts to reuse from earlier phases

- Native Windows environment, Node 22, no WSL2 — see
  `docs/phase-0-environment-setup/CLAUDE.md`.
- `api/package.json` already lists the needed dependencies
  (express, helmet, morgan, bcryptjs, jsonwebtoken, pg, dotenv) — run
  `npm install` inside `api/` rather than re-adding packages.
- `.env.example` already defines `PORT`, `DATABASE_URL`, `JWT_SECRET` —
  reuse these variable names in `api/config/index.js`.

## When this phase is done

Fill in `IMPLEMENTATION.md`, `MEMORY.md`, `FILES.md` in this folder with the
same what/why/how depth as Phase 0/1, then update this file's status to
Complete.
