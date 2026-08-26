# Intelligent Threat Detection & Prevention in REST APIs Using ML

MSc Cyber Security dissertation artefact (CB016639). A hybrid rule-based +
machine-learning detection framework for REST APIs, targeting SQL injection,
brute force, and credential stuffing attacks in real time.

## Current Status

This repository is in mid-to-late implementation.

- Phase 0 scaffolding is present.
- Phase 1 dataset preprocessing and the canonical ML feature contract are
  implemented (`ml/features.py`, `ml/preprocess.py`).
- Phase 2 REST API, Phase 3 rule-based detection middleware, Phase 4 model
  training, Phase 5 inference service and Phase 6 hybrid integration are all
  implemented and verified.
- Phase 7 Docker Compose brings the three services up together.
- Phase 8 attack simulation is complete, and resolved the earlier
  false-positive blocker.
- Phases 9-10 remain: comparative evaluation, and the final documentation and
  AWS write-up.

Measured results are in `evaluation/results.md`. The hybrid catches attacks the
rules miss, and Phase 8 brought its false positive rate on this API's own benign
traffic from 17.5% down to 1.8% — by finding, with representative traffic, that
the payload classifier was mis-scoring credential login bodies as attacks, and
scoping it to the endpoints where a payload model has signal.

**To see it run,** follow `DEMO_GUIDE.md` — a start-to-finish walkthrough that
brings the whole stack up in Docker and demonstrates all three attacks being
detected, with nothing installed but Docker.

**Setting this up on a different machine for someone with no prior context?**
Use `QUICKSTART.md` instead — a short, assumption-free guide covering
installing Docker Desktop, unzipping the pre-built `shipping-kit.zip`, and
running the demonstration, written for someone who has never touched this
project before.

See `docs/PROJECT_STATUS.md` for the phase-by-phase status and review notes.

## Architecture

```
Request -> Feature Extraction -> Rule Filter (fast) -> ML Classifier (adaptive) -> Weighted Score -> Allow / Block
```

- **api/** - Node.js/Express REST API with vulnerable + secured endpoints, and the
  detection middleware (feature extraction, rule engine, ML client).
- **ml/** - Python/FastAPI inference service hosting Random Forest, XGBoost, and
  Isolation Forest models, plus the training/evaluation pipeline.
- **datasets/** - Raw and processed research datasets (gitignored; see
  `datasets/README.md` for acquisition instructions).
- **attack-sim/** - Self-contained attack traffic generators used to evaluate
  detection performance against our own local API only.
- **evaluation/** - Generated figures and results tables for the dissertation.

## Environment

Developed and run natively on Windows 11 with Docker Desktop. Node.js 22 and
Python 3.13 are used locally (functionally equivalent to the Node 20 / Python
3.11 versions referenced in the build spec). The API and ML services run as
Linux containers (`node:22-slim`, `python:3.13-slim` base images) under Docker
Compose for the evaluation runtime, so the deployed artefact is Linux-based
regardless of host OS.

## Running the Stack

The whole system runs under Docker Compose:

```powershell
docker compose up --build
```

That starts PostgreSQL, the inference service and the API, in that order — the
API waits for both dependencies to report healthy, so a request never reaches a
service that has not finished loading. The API is then on
<http://localhost:3000>.

**Prerequisite:** `ml/models/` must contain trained artefacts. They are
bind-mounted rather than baked into the image, because the Random Forest alone
is 259 MB and none of them are in version control. From a fresh clone, place the
raw datasets (see `datasets/README.md`) and run:

```powershell
python -m venv ml/venv
.\ml\venv\Scripts\python -m pip install -r ml\requirements.txt
.\ml\venv\Scripts\python ml\preprocess.py
.\ml\venv\Scripts\python ml\train.py
```

Behaviour is selected by environment variable, which is how the Phase 9
evaluation builds its comparison configurations without code changes:

| Variable | Default | Effect |
|---|---|---|
| `DETECTION_MODE` | `hybrid` | `off`, `rules`, `hybrid` |
| `DETECTION_THRESHOLD` | `0.7` | Combined score at which a request is blocked |
| `COMBINE_STRATEGY` | `noisy_or` | `noisy_or`, `weighted`, `max`, `rules_only` |
| `ML_TIMEOUT_MS` | `250` | Inference timeout before falling back to rules |
| `DETECTION_TRACE` | `0` | Set to `1` to log the score breakdown per request |

## Running Components Individually

The preprocessing code can be run after the raw datasets have been placed under
`datasets/raw/`:

```powershell
python -m venv ml/venv
.\ml\venv\Scripts\python -m pip install -r ml\requirements.txt
.\ml\venv\Scripts\python ml\preprocess.py
```

The preprocessing output is written to `datasets/processed/`, which is
gitignored because it is generated and large. See `datasets/README.md` for the
expected local dataset layout.

The API can be run standalone, without Docker:

```powershell
cd api
npm install
copy ..\.env.example .env
node server.js
```

For the hybrid path it needs the inference service alongside it, started from
`ml/`:

```powershell
..\ml\venv\Scripts\python -m uvicorn app:app --port 8000
```

Verification scripts:

```powershell
node api/test/featureParity.js        # JS and Python feature contracts agree
node api/test/hybridIntegration.js    # end-to-end; --no-ml for the fail-open path
.\ml\venv\Scripts\python ml\test_inference.py
```

`GET /health`, `POST /api/auth/register`, `POST /api/auth/login`,
`GET /api/search/vulnerable?q=`, `GET /api/search/secure?q=`, and
`GET /api/orders/:id` are all reachable. See `api/test/endpoints.http` for
sample requests. Auth is in-memory only (resets on restart); Postgres
logging in `api/db/pool.js` writes to the `request_log` table when the
stack is running under Compose, and fails soft when it is not.

## Ethics

All attack traffic is generated by our own scripts against our own local API.
All datasets are publicly available research datasets used under their
licences. No real malware, no real user data, no live or third-party systems
are involved. Everything runs locally in Docker on the researcher's machine.
