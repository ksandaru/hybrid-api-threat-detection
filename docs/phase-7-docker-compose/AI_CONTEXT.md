# Phase 7 — AI Context

## Original spec goal

> `docker compose up` brings up API + ML + Postgres together.

## Tasks (as written)

1. `docker-compose.yml` with three services: `api` (build `./api`, port
   3000, env `ML_SERVICE_URL=http://ml:8000`), `ml` (build `./ml`, port
   8000), `db` (postgres:15, credentials from `.env`).
2. Make `api` depend on `ml` and `db`. Use a Docker network so `api`
   reaches `ml` by service name.
3. Update `README.md` with run instructions.

## Deliverable check (as written)

Fresh `docker compose up --build` → all three healthy → end-to-end attack
detection works through the containerised stack.

## Suggested commit message (as written)

`feat: docker-compose orchestration for full stack`

## Status

**Not started.** Note: `docker-compose.yml` currently exists only as a
Phase 0 TODO stub.
