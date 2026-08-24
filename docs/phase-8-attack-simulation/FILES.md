# Phase 8 — Files Created / Modified

| File | Purpose |
|---|---|
| `attack-sim/common.py` | Shared harness: `Client` (synthetic source, score capture), `Recorder` (labelled CSV), `preflight`/`check_trust_proxy` |
| `attack-sim/benign_traffic.py` | Representative benign traffic, including the punctuation/encoding/keyword-substring cases that stress a payload detector |
| `attack-sim/sqli_attack.py` | Six SQLi families, labelled by sub-type; per-family detection reporting |
| `attack-sim/brute_force.py` | Single-username password guessing; records the attempt blocking began |
| `attack-sim/credential_stuffing.py` | Many synthetic usernames, one attempt each; fixed-seed pairs, never real data |
| `attack-sim/run_all.py` | Runs the four in sequence, waiting for a clean window (or restarting the API) between each |
| `attack-sim/recalibrate_threshold.py` | Sweeps the decision threshold on the generated traffic; reports FPR/recall and the per-endpoint breakdown; writes the recalibration report |
| `attack-sim/requirements.txt` | `requests` for the harness |
| `api/config/index.js` | Modified — added `trustProxy` and `mlPayloadPaths` |
| `api/server.js` | Modified — honours `TRUST_PROXY`, with a loud warning |
| `api/middleware/detection.js` | Modified — ML consulted only on payload-bearing endpoints; trace headers on every response |
| `docker-compose.yml` | Modified — passes `TRUST_PROXY` through to the api service |
| `.gitignore` | Modified — ignore `evaluation/traffic/*.csv`, keep `.gitkeep` |
| `evaluation/threshold_recalibration.md` | Generated report — the recalibration finding and curve (committed) |
| `evaluation/traffic/*.csv` | Generated per-request traffic logs (gitignored; reproducible from fixed seeds) |

## Run

Bring the stack up with the simulation flags:

```powershell
$env:TRUST_PROXY=1; $env:DETECTION_TRACE=1; docker compose up -d --build
```

Generate all traffic, then recalibrate:

```powershell
python attack-sim/run_all.py
python attack-sim/recalibrate_threshold.py
```

Or one generator at a time (each refuses to run against a dirty 60s window):

```powershell
python attack-sim/benign_traffic.py
python attack-sim/sqli_attack.py
python attack-sim/brute_force.py
python attack-sim/credential_stuffing.py
```

## Inspect

Per-request logs are in `evaluation/traffic/`, one CSV per generator, columns:
`expected_label`, `attack_type`, `status`, `blocked`, `score`, `rule_score`,
`ml_score`, `alerts`, `latency_ms`. The recalibration report is written to
`evaluation/threshold_recalibration.md`.
