# Project Status

Last reviewed: Phase 3 update

This document records the current implementation state after the initial
Claude-generated phases. It is meant to keep the README, phase docs, and source
tree aligned while later phases are being implemented.

## Phase Status

| Phase | Area | Status | Notes |
|---|---|---|---|
| 0 | Environment and scaffold | Complete | Directory structure, Dockerfiles, env example, placeholder files, and phase docs exist. |
| 1 | Dataset preprocessing | Complete | `ml/features.py` and `ml/preprocess.py` implement the canonical feature contract and dataset unification. `train.parquet` (677,166 rows) and `heldout_atrdf.parquet` (540,057 rows) generated; stats in `evaluation/results.md`. |
| 2 | REST API | Complete | `api/server.js`, auth/search/orders routes, config, and DB pool are implemented and manually verified with curl (login 200/401, vulnerable search 200, orders 401/200). `request_log` table doesn't exist yet — Phase 7 needs to create it. |
| 3 | Rule middleware | Complete | Feature extractor (mirrors `ml/features.py`, parity-tested), 15-rule engine, and orchestrator mounted at `/api`. Verified live: benign passes, 4 SQLi variants blocked, brute force blocks from attempt 4, credential stuffing from the 5th username. `DETECTION_MODE` switch added for Phase 9 baselines. |
| 4 | Model training | Not started | `ml/train.py` is a TODO stub; no model artifacts should be expected yet. |
| 5 | FastAPI inference | Not started | `ml/app.py` is a TODO stub and cannot serve predictions yet. |
| 6 | Hybrid integration | Not started | API-to-ML client and score combination are TODO stubs. |
| 7 | Docker Compose runtime | Not started | `docker-compose.yml` is intentionally a placeholder until services can run. |
| 8 | Attack simulation | Not started | Traffic generator scripts are TODO stubs. |
| 9 | Evaluation | Not started | `ml/evaluate.py` is a TODO stub; only Phase 1 dataset statistics are documented. |
| 10 | Final documentation | In progress | Root README and dataset docs now reflect the current state; AWS write-up is still a TODO stub. |

## Review Findings

- The previous README implied that `docker compose up --build` was ready. That
  was inaccurate because the Compose file and service entry points are still
  placeholders.
- `.gitignore` now covers common Python, Node, notebook, editor, log, model,
  figure, secret, dataset, and virtual-environment artifacts while preserving
  required `.gitkeep` files and allowing `ml/models/feature_order.json` to be
  tracked later.
- `datasets/README.md` now documents the expected local raw dataset layout and
  clarifies that ATRDF 2023 is held out from training.
- Git reports `C:\Users\hp\.config\git\ignore` as unreadable on this machine.
  That is a local/global Git configuration permission issue, not a repository
  `.gitignore` issue.

## Next Implementation Order

1. Implement Phase 4 training and save `feature_order.json` plus model
   artifacts under `ml/models/`.
2. Implement Phase 5 inference after trained artifacts exist.
3. Wire Phase 6 integration at the marked insertion point in
   `api/middleware/detection.js`, then Phase 7 Compose once both services run
   independently. Phase 7 also needs to create the `request_log` table that
   `api/db/pool.js` already expects.
