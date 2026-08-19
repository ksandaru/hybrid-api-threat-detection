# Phase 7 — Resume Notes for Claude Code

Status: **Complete.** `docker compose up --build` from a clean slate brings all
three services healthy and detection works end to end through the containers.

## Facts to reuse

- **Models are bind-mounted, not in the image.** `ml/models/` must be populated
  before the stack will start. If the inference service reports unhealthy, check
  that directory first.
- **Health checks test readiness.** The ML probe reads the `ready` field, not the
  status code, because the service answers 200 while still loading.
- **The schema is created by `db/init/01_schema.sql` on first volume
  initialisation.** Editing it has no effect on an existing volume; run
  `docker compose down -v` to re-run it.
- **Behaviour is environment-driven.** Phase 9 builds all four comparison
  configurations from `DETECTION_MODE` and `COMBINE_STRATEGY` on the `api`
  service without touching code.

## For Phase 9

- **Degraded-mode latency is not free under Compose.** A stopped container
  swallows connections rather than refusing them, so the fail-open path costs
  the full `ML_TIMEOUT_MS` (250 ms) per request, against about 3 ms when the
  process is merely dead locally. Report degraded latency separately, and
  consider lowering the timeout.
- **`request_log` is the evaluation record.** Every inspected request is stored
  with its full feature vector as JSONB and its decision, indexed by time,
  decision and source. Reconstruct attack sequences from there rather than
  re-parsing container logs.
- **The ModSecurity baseline still needs adding** as a fourth service, in front
  of a copy of the API with detection disabled (`DETECTION_MODE=off`), so the
  comparison is like for like.

## Traps

- `${VAR:-}` in Compose sets an empty string, not an unset variable. Any new
  numeric environment override must tolerate `""`, or it will start cleanly
  locally and fail only under Compose. This already cost one debugging cycle.
- `depends_on` without `condition: service_healthy` waits for the container, not
  the process inside it.
- Rebuilding after changing `ml/app.py` requires `docker compose up -d --build ml`;
  a plain restart reuses the old image.
