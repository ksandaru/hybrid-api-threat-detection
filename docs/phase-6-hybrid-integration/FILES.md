# Phase 6 — Files Created / Modified

| File | Purpose |
|---|---|
| `api/middleware/mlClient.js` | Inference client. Short timeout, never throws, rate-limited failure logging, discovers the service decision boundary from `/meta` |
| `api/middleware/scoreCombiner.js` | Combination logic. Rescales the ML score to a common decision scale, then applies one of four strategies (`noisy_or` default, `weighted`, `max`, `rules_only`) |
| `api/middleware/detection.js` | Modified — async; calls inference when mode is `hybrid` and no high-severity rule fired; combines; falls back to the rule verdict on any failure |
| `api/test/hybridIntegration.js` | Integration check for both configurations (`--no-ml` for the fail-open path) |
| `evaluation/results.md` | Phase 6 section added |

## Configuration

| Variable | Default | Effect |
|---|---|---|
| `DETECTION_MODE` | `rules` | `off`, `rules`, `hybrid` |
| `DETECTION_THRESHOLD` | `0.7` | Combined score at which a request is blocked |
| `COMBINE_STRATEGY` | `noisy_or` | `noisy_or`, `weighted`, `max`, `rules_only` |
| `W_RULE`, `W_ML` | `0.5`, `0.5` | Weights, used only by the `weighted` strategy |
| `ML_TIMEOUT_MS` | `250` | Inference timeout before falling back to rules |
| `DETECTION_TRACE` | unset | Set to `1` to log rule score, ML raw and aligned score, combined score and decision per request |

## Run

Start the inference service from `ml/`:

```powershell
..\ml\venv\Scripts\python -m uvicorn app:app --port 8000
```

Start the API in hybrid mode from `api/`:

```powershell
$env:DETECTION_MODE="hybrid"; node server.js
```

Then, from the repository root:

```powershell
node api/test/hybridIntegration.js
```

Stop the inference service and re-run with `--no-ml` to exercise the fail-open
path. Both configurations currently pass all checks.
