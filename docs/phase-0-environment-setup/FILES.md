# Phase 0 — Files Created / Modified

All paths relative to the repo root (`hybrid-api-threat-detection/`).

| File | Purpose |
|---|---|
| `.gitignore` | Excludes node_modules, venvs, trained models, raw/processed datasets, secrets, logs, generated figures |
| `.env.example` | Documents required environment variables without committing real secrets |
| `README.md` | Project overview, architecture summary, environment notes, run instructions |
| `docker-compose.yml` | Stub — wired up fully in Phase 7 |
| `api/package.json` | Node dependency manifest (express, helmet, morgan, bcryptjs, jsonwebtoken, axios, pg, dotenv) |
| `api/Dockerfile` | Node 22-slim container build for the API service |
| `api/server.js` | Stub — Express bootstrap, built in Phase 2/3 |
| `api/config/index.js` | Stub — centralised env config, built in Phase 2 |
| `api/routes/auth.js` | Stub — login/register endpoints, built in Phase 2 |
| `api/routes/search.js` | Stub — SQLi-vulnerable/secure search endpoints, built in Phase 2 |
| `api/routes/orders.js` | Stub — protected resource endpoint, built in Phase 2 |
| `api/middleware/detection.js` | Stub — detection orchestrator, built in Phase 3/6 |
| `api/middleware/featureExtractor.js` | Stub — request feature extraction, built in Phase 3 |
| `api/middleware/ruleEngine.js` | Stub — rule-based fast path, built in Phase 3 |
| `api/middleware/mlClient.js` | Stub — ML service HTTP client, built in Phase 6 |
| `api/db/pool.js` | Stub — Postgres pool + request logging, built in Phase 2 |
| `api/test/endpoints.http` | Stub — manual REST-client test requests, built in Phase 2 |
| `ml/requirements.txt` | Python dependency manifest (fastapi, scikit-learn, xgboost, imbalanced-learn, pandas, etc.) |
| `ml/Dockerfile` | Python 3.13-slim container build for the ML inference service |
| `ml/app.py` | Stub — FastAPI inference server, built in Phase 5 |
| `ml/train.py` | Stub — model training script, built in Phase 4 |
| `ml/features.py` | Stub — canonical shared feature contract, built in Phase 1 |
| `ml/preprocess.py` | Stub — dataset cleaning/unification, built in Phase 1 |
| `ml/evaluate.py` | Stub — comparative evaluation, built in Phase 9 |
| `ml/notebooks/01_explore.ipynb` | Stub notebook for dataset exploration, built in Phase 1 |
| `ml/models/.gitkeep` | Keeps the (gitignored) trained-model directory present on clone |
| `datasets/README.md` | Dataset acquisition instructions and provenance notes |
| `datasets/raw/.gitkeep`, `datasets/processed/.gitkeep` | Keep gitignored dataset directories present on clone |
| `attack-sim/sqli_attack.py`, `brute_force.py`, `credential_stuffing.py`, `benign_traffic.py` | Stubs — attack/benign traffic generators, built in Phase 8 |
| `evaluation/results.md` | Stub — dissertation-ready results write-up, built across Phases 1/4/9 |
| `evaluation/figures/.gitkeep` | Keeps the (gitignored) generated-figures directory present on clone |
| `docs/deployment-aws-feasibility.md` | Stub — written-only AWS deployment discussion, built in Phase 10 |

## Git / tooling changes (not files, but repo state)

- `git config user.name` / `user.email` set locally to this repo.
- `git config core.autocrlf true` set locally to this repo.
- Root commit created: `chore: scaffold monorepo structure and tooling`.
