# Phase 7 — Implementation Log

Status: **Complete.** `docker compose up --build` from a clean slate brings all
three services to healthy and detection works end to end through the containers.

---

### Step 1 — Keep the build contexts small

- **What:** Added `.dockerignore` to both `api/` and `ml/`.
- **Why:** The `ml/` build context contains a 600 MB virtualenv and 220 MB of
  trained models, and `api/` contains `node_modules`. Docker sends the entire
  context to the daemon before the first instruction runs, so without these the
  build would transfer close to a gigabyte on every invocation and bake host
  artefacts into the image.
- **How:** `ml/.dockerignore` excludes `venv/`, `models/`, `__pycache__` and the
  notebooks; `api/.dockerignore` excludes `node_modules`, `.env` and the test
  directory.

### Step 2 — Decide how models reach the container

- **What:** Models are bind-mounted read-only at `/usr/src/app/models` rather
  than copied into the image.
- **Why:** Two reasons, either sufficient. The Random Forest alone is 259 MB, so
  copying it would produce an image far larger than the code it serves. More
  fundamentally, the models are not in version control, so a fresh clone could
  not build an image containing them — the build would either fail or silently
  produce a service with no models.
- **How:** A read-only volume in `docker-compose.yml`, with the prerequisite
  documented in the README and at the top of the Compose file. The Dockerfile
  creates the mount point so the service can report a clear error if the
  directory is empty rather than failing obscurely.

### Step 3 — Database schema

- **What:** `db/init/01_schema.sql`, mounted into the Postgres image's
  initialisation directory.
- **Why:** `api/db/pool.js` has written to `request_log` since Phase 2, but
  nothing ever created the table. The write path fails soft, so its absence
  degraded analysis rather than detection, and it went unnoticed until there was
  a database to notice it with.
- **How:** Table plus four indexes — `created_at`, `decision` and `ip` because
  Phase 9 reconstructs attack sequences by time, outcome and source, and a GIN
  index on the JSONB features column so individual features can be queried when
  analysing which signal drove a decision. Scripts in that directory run once
  on first initialisation of an empty volume, so `docker compose down -v`
  re-runs them.

### Step 4 — Health checks and start ordering

- **What:** Health checks on all three services, with the API declaring
  `depends_on: condition: service_healthy` for both dependencies.
- **Why:** `depends_on` alone waits for a container to start, not for the
  process inside it to be ready. The inference service takes roughly 40 seconds
  to load the Random Forest, and an API that began accepting traffic during that
  window would fail every request to a service that was running but not ready.
- **How:** `pg_isready` for the database, an HTTP probe for the API, and for the
  inference service a probe that checks the `ready` field rather than the status
  code — the service answers `/health` with `200` while artefacts are still
  loading, so a status-code check would have reported ready too early. The ML
  check uses a 40-second start period to cover model loading.

### Step 5 — Verification, and the bug it found

First `docker compose up` failed: the database came up healthy, the inference
service reported unhealthy, and the API refused to start because its dependency
was unhealthy — which is the ordering working correctly.

Querying the container's own health endpoint gave:

    "error": "ValueError: could not convert string to float: ''"

The Compose file passed the optional weight overrides as `${W_RF:-}`. That
expansion does not leave the variable unset; it sets it to an **empty string**.
`os.getenv("W_RF", default)` therefore returned `""` rather than the default,
and `float("")` raised during artefact loading.

This is a deployment-only failure. The same code runs correctly outside
containers, because nothing sets those variables there. Fixed in `ml/app.py`
with a helper that treats unset and empty as equivalent and falls back to the
value from the trained artefact, warning rather than failing on a non-numeric
value. An optional override that is merely not in use must not stop a service
from starting.

---

## Deliverable check

From a clean slate, including removal of the data volume:

```
docker compose down -v
docker compose up --build
```

| Service | Status |
|---|---|
| db | Up (healthy) |
| ml | Up (healthy) |
| api | Up (healthy) |

End-to-end detection through the containers passes every check: benign traffic
served, all three rule-catchable attacks blocked, the attack the rules miss
blocked at 0.96 with the classifier consulted, and brute force blocked. Latency
p95 stays inside the 100 ms budget.

Request logging now persists. After a run, 28 rows across `allowed` and
`blocked`, with the feature vector queryable as JSONB:

```sql
SELECT path, decision, features->>'sql_keyword_count', features->>'requests_per_min_ip'
FROM request_log WHERE decision='blocked';
```

The schema is recreated automatically on a fresh volume, so the reproducibility
claim holds rather than depending on a manually prepared database.

## Fail-open costs more in containers than it did locally

Stopping the inference container and repeating the checks: the API stays
healthy, keeps serving benign traffic, and continues blocking rule-catchable
attacks. Only ML-dependent detection is lost, which is the intended behaviour.

One measured difference is worth carrying into Phase 9. Locally, stopping the
service produced `ECONNREFUSED` and the fallback cost about 3 ms. With the
container stopped, the connection is not refused — it hangs until the client
gives up, so the fallback costs the full 250 ms timeout. Under Compose an
inference outage therefore adds roughly 250 ms per request rather than being
nearly free.

That does not change correctness, but it means the latency figures reported
during an outage depend on how the dependency fails, and the 250 ms timeout is
now a directly load-bearing number rather than a safety margin. Phase 9 should
report degraded-mode latency separately and may want to lower the timeout.
