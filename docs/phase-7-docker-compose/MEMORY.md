# Phase 7 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **Models are bind-mounted, not copied into the image.** The Random Forest is
  259 MB, and none of the artefacts are in version control, so a fresh clone
  could not build an image containing them. Mounting keeps the image close to
  the size of the code it serves, and makes the "train first" prerequisite
  explicit rather than producing an image that silently has no models.
- **Health checks test readiness, not liveness.** The inference service answers
  `/health` with 200 while it is still loading roughly 260 MB of artefacts, so a
  status-code check reports ready about 40 seconds too early. The probe reads
  the `ready` field instead, and the API waits on `service_healthy` for both
  dependencies.
- **Schema lives in `db/init/`, run by the Postgres image on first start.** No
  migration tool for a single-table artefact; `docker compose down -v` re-runs
  it, which is what makes the reproducibility claim testable rather than
  assumed.
- **GIN index on the JSONB features column.** Phase 9 needs to ask which feature
  drove a decision, not only what the decision was.
- **Containers run as non-root.** Running as root inside a container that
  deliberately terminates untrusted input would be a poor advertisement for a
  security dissertation.
- **`npm ci` rather than `npm install`.** It honours the lock file exactly,
  which is what makes a rebuild reproducible.

## Gotchas

- **`${VAR:-}` in Compose sets an empty string; it does not leave the variable
  unset.** `os.getenv("W_RF", default)` then returns `""` rather than the
  default, and `float("")` raises. This failed only under Compose — the same
  code runs fine locally, because nothing sets those variables there. Any
  optional numeric override read from the environment must treat unset and empty
  as equivalent.
- **`depends_on` without `condition: service_healthy` waits for the container,
  not the process inside it.** With a 40-second model load, that difference is
  the entire startup window.
- **A stopped container does not refuse connections, it swallows them.**
  Locally, killing the inference process gave `ECONNREFUSED` and the fail-open
  path cost about 3 ms. With the container stopped the connection hangs until
  the client gives up, so the same fallback costs the full 250 ms timeout.
  Fail-open cost depends on *how* the dependency fails, and `ML_TIMEOUT_MS` is
  load-bearing under Compose in a way it was not locally.
- **The build context is sent to the daemon before the first instruction runs.**
  Without `.dockerignore`, the `ml/` context alone would ship 820 MB of
  virtualenv and models on every build.

## Open items

- Phase 9 should report degraded-mode latency separately, and may want to lower
  `ML_TIMEOUT_MS` now that an outage costs the full timeout per request rather
  than failing fast.
- The database port is published to the host for inspection during evaluation.
  Convenient here, inappropriate in a real deployment.
- Credentials default to the values in `.env.example`. Acceptable for a local
  evaluation artefact, and worth naming in the AWS write-up as one of the things
  that would change in a real deployment.
