# Project Status

Last reviewed: after the Phases 0-7 hardening pass

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
| 6 | Hybrid integration | Complete | Pipeline runs end to end. Deliverable met: an attack rules miss (0.500) is blocked at 0.96 with the classifier. Fail-open verified. Combination is a noisy-OR, not a weighted mean, because a weighted mean would cancel rule verdicts on behavioural attacks. ~~Blocker: hybrid FPR 33% vs rules-only 0% on benign traffic.~~ **Resolved in Phase 8** by scoping ML to payload endpoints; benign FPR now 1.8%. |
| 7 | Docker Compose runtime | Complete | `docker compose up --build` from a clean slate brings db, ml and api to healthy and detection works end to end through the containers. Models bind-mounted (46 MB compressed, not in git). `request_log` schema created on first volume init - the gap open since Phase 2 is closed and logging verified. Measured footprint: ml 596 MB resident, api 38 MB, db 29 MB. |
| - | Hardening pass (0-7) | Complete | Sliding-window memory leak fixed; SIGTERM/SIGINT draining added; two integration-test defects that produced misleading failures corrected; all 11 config variables documented; npm test entry points added; parity test made container-runnable. Detection behaviour unchanged. **Random Forest depth constraint was measured and rejected** - every variant roughly doubled payload FPR, though ROC AUC improved, so an AUC-led choice would have picked the worse deployment. Size solved with `joblib compress=3` instead: 230 MB to 46 MB, and loading got faster. See `evaluation/results.md`. |
| 8 | Attack simulation | Complete | Four generators (`attack-sim/`) produce labelled attack + benign traffic, each request logging its score. **Resolved the Phase 6 blocker:** benign traffic showed the 17.5% FPR was concentrated on auth endpoints (21/25) because the payload classifier scores credential bodies as attacks. Fixed by scoping ML to payload-bearing endpoints (`config.mlPayloadPaths`). Benign FPR 17.5% -> 1.8%, SQLi 100%, behavioural attacks now caught by the rules (attempt/username 5) not the ML artefact. `evaluation/threshold_recalibration.md` records the analysis. |
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

1. ~~Phase 8 attack and benign traffic generation.~~ **Done.** Generators built,
   the Phase 6 blocker resolved by scoping ML to payload endpoints (not by a
   threshold move, which the traffic showed could not work).
2. Phase 9 evaluation. Build the four configurations from `DETECTION_MODE` and
   `COMBINE_STRATEGY`; compare all four combination strategies; report rule-only
   and hybrid false positive rates side by side rather than accuracy alone;
   decide the 0.7-vs-0.8 threshold here across all configurations rather than
   setting it in Phase 8; run the held-out ATRDF set (never trained on) for
   cross-dataset generalisation; report degraded-mode latency separately, since
   a stopped container costs the full 250 ms timeout per request; and add
   ModSecurity as a fourth Compose service in front of an API running with
   `DETECTION_MODE=off`. The Phase 8 harness already gives each client a distinct
   source identity, so the request-rate self-trip is handled.
3. Phase 10 documentation and the written-only AWS feasibility section.

## Deployment decision (recorded, not yet acted on)

Everything continues to run locally for now. Model training and evaluation may
later move to Google Colab, with the trained artefacts downloaded and used by
the API exactly as they are today. That works without changing the pipeline:
training is a four-minute CPU job, the artefacts total 46 MB, and `ml/app.py`
already reads its weights and threshold from the artefact rather than from code.

If any part of this is ever hosted publicly, the deliberately vulnerable
endpoint `/api/search/vulnerable` must not be. It never executes the query it
builds, but a publicly reachable intentionally-vulnerable endpoint contradicts
the ethics statement and would let traffic nobody generated contaminate
`request_log`, which is the evaluation record. The inference service is safe to
expose - it accepts a feature vector and returns a score.
