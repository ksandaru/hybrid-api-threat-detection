# Project Status

Last reviewed: Phase 7 update

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
| 4 | Model training | Complete | RF / XGBoost / Isolation Forest trained and saved with scaler and `feature_order.json`. Retrained in Phase 5 with a three-way split: test acc 0.916-0.965, ROC AUC up to 0.976; CV agrees within 0.001. **Key finding: 4 flow features have zero importance (zero-filled in the corpus), so the models cannot detect brute force or credential stuffing** - see `evaluation/results.md`. |
| 5 | FastAPI inference | Complete | `ml/app.py` serves `/health`, `/meta`, `/predict` with weighted RF+XGB+IF scoring. Threshold 0.77 selected on a validation split (three-way split introduced here). Combined pipeline beats every single model: F1 0.8433 overall, 0.9357 on payload traffic. **Report FPR on payload-bearing rows (5.96%) as well as aggregate (0.87%)** - the aggregate is flattered by flow records. |
| 6 | Hybrid integration | Complete | Pipeline runs end to end. Deliverable met: an attack rules miss (0.500) is blocked at 0.96 with the classifier. Fail-open verified. Combination is a noisy-OR, not a weighted mean, because a weighted mean would cancel rule verdicts on behavioural attacks. **Blocker: hybrid FPR 33% vs rules-only 0% on benign traffic - not deployable until Phase 8 recalibrates on representative traffic.** |
| 7 | Docker Compose runtime | Complete | `docker compose up --build` from a clean slate brings db, ml and api to healthy and detection works end to end through the containers. Models bind-mounted (259 MB RF, not in git). `request_log` schema created on first volume init - the gap open since Phase 2 is closed and logging verified. |
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

1. Phase 8 attack and benign traffic generation. This is also the fix point for
   the Phase 6 blocker: generate representative benign traffic, then re-select
   the ML decision threshold on it. The current 0.77 was chosen on corpus
   validation rows that do not cover this API's traffic shape.
2. Phase 9 evaluation. Build the four configurations from `DETECTION_MODE` and
   `COMBINE_STRATEGY`; compare all four combination strategies; report rule-only
   and hybrid false positive rates side by side rather than accuracy alone; give
   each simulated client a distinct source identity so the harness does not trip
   the request-rate rules and measure its own load; report degraded-mode latency
   separately, since a stopped container costs the full 250 ms timeout per
   request; and add ModSecurity as a fourth Compose service in front of an API
   running with `DETECTION_MODE=off`.
3. Phase 10 documentation and the written-only AWS feasibility section.
