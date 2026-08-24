# Phase 3 — Files Created / Modified

| File | Purpose |
|---|---|
| `api/middleware/featureExtractor.js` | JavaScript half of the shared feature contract: 12 payload features, per-source sliding window supplying 5 flow features, canonical ordering, request-to-text assembly |
| `api/middleware/ruleEngine.js` | 15 rules over the feature vector; returns `{ blocked, alerts, ruleScore }`; thresholds and rule set exported for Phase 9 sweeps |
| `api/middleware/detection.js` | Orchestrator: extract, evaluate, block or continue, log off the critical path; `DETECTION_MODE` switch |
| `api/test/featureParity.js` | Executes both feature implementations over 20 payloads and fails on divergence (240 comparisons) |
| `api/server.js` | Modified — mounts the detection middleware at `/api` ahead of all routes |
| `api/config/index.js` | Modified — adds `detectionMode` (`off`, `rules`, `hybrid`) |

## Verification commands

```powershell
node api/test/featureParity.js
```

Contract parity between the JavaScript and Python feature implementations.
Exits non-zero on any divergence.

```powershell
cd api
node server.js
```

Then exercise the endpoints as recorded in `IMPLEMENTATION.md`. Set
`DETECTION_TRACE=1` before starting the server to log the score, decision and
rules fired for every request.
