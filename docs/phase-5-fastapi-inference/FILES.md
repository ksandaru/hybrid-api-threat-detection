# Phase 5 — Files Created / Modified

| File | Purpose |
|---|---|
| `ml/app.py` | FastAPI inference service: `/health`, `/meta`, `/predict`. Loads artefacts once, orders features canonically, normalises the Isolation Forest score, returns the weighted score with per-model detail and latency |
| `ml/test_inference.py` | Deliverable check: asserted distributional comparison against 600 corpus rows, plus reported-only illustrative cases |
| `ml/train.py` | Modified — three-way split, Isolation Forest calibration percentiles, validation-selected operating point, combined-pipeline metrics |
| `evaluation/results.md` | Phase 4 figures refreshed for the three-way split; Phase 5 section added |
| `ml/Dockerfile` | Unchanged from Phase 0 (`python:3.13-slim`, uvicorn) |

## Artefact additions

`ml/models/feature_order.json` (tracked in git) now carries three things rather
than one:

```json
{
  "feature_order": [ ... 17 names ... ],
  "iso_calibration": { "p1": 0.2988, "p99": 0.7704, "median": 0.2988 },
  "operating_point": {
    "weights": { "random_forest": 0.4, "xgboost": 0.4, "isolation_forest": 0.2 },
    "selected_threshold": 0.77,
    "threshold_fpr_5pct": 0.78,
    "selected_on": "validation split, payload-bearing sources"
  }
}
```

The service reads all three, so scoring cannot drift from what was measured.

## Run

Start the service from `ml/`:

```powershell
..\ml\venv\Scripts\python -m uvicorn app:app --port 8000
```

Then, from the repository root:

```powershell
.\ml\venv\Scripts\python ml\test_inference.py
```

Exits non-zero if the service stops reproducing the offline measurement.
Environment overrides `W_RF`, `W_XGB`, `W_ISO` and `ML_ATTACK_THRESHOLD` exist
for Phase 9 sweeps.
