# Phase 7 — Files Created / Modified

| File | Purpose |
|---|---|
| `docker-compose.yml` | Three services with health checks, ordered startup, a private bridge network, and environment-driven behaviour selection |
| `db/init/01_schema.sql` | `request_log` table plus four indexes; run once on first initialisation of an empty volume |
| `api/.dockerignore` | Keeps `node_modules`, `.env` and tests out of the build context |
| `ml/.dockerignore` | Keeps the 600 MB virtualenv and 220 MB of models out of the build context |
| `api/Dockerfile` | Modified — `npm ci`, non-root user, health check |
| `ml/Dockerfile` | Modified — non-root user, readiness health check, model mount point |
| `ml/app.py` | Modified — empty environment overrides no longer fatal |
| `README.md` | Rewritten run instructions and configuration table |

## Run

```powershell
docker compose up --build
```

Prerequisite: `ml/models/` must contain trained artefacts, which are
bind-mounted rather than baked into the image. See the README for how to produce
them from a fresh clone.

## Inspect

```powershell
docker compose ps
docker compose logs -f api
```

Query the evaluation record:

```powershell
docker compose exec db psql -U detector -d api_threat_detection -c "SELECT decision, count(*) FROM request_log GROUP BY decision;"
```

## Configuration

Set on the `api` service and overridable from the environment:
`DETECTION_MODE`, `DETECTION_THRESHOLD`, `COMBINE_STRATEGY`, `ML_TIMEOUT_MS`,
`DETECTION_TRACE`.

The `ml` service additionally accepts `W_RF`, `W_XGB`, `W_ISO` and
`ML_ATTACK_THRESHOLD`, which default to the values recorded in the trained
artefact when left unset.
