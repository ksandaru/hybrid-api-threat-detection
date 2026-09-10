# User Manual

Operating guide for the hybrid API threat detection framework, v1.0.0.

This covers running the system **natively**, with a Python virtual environment
and npm — no Docker. If you would rather use containers, `README.md` has the
Compose route.

For what the system *is* and what it measured, read `README.md` and
`RELEASE_NOTES.md`. This document is about running it.

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [First-time setup](#2-first-time-setup)
3. [Starting the system](#3-starting-the-system)
4. [Checking it works](#4-checking-it-works)
5. [Configuration reference](#5-configuration-reference)
6. [Running a demonstration](#6-running-a-demonstration)
7. [Regenerating the results](#7-regenerating-the-results)
8. [Verification suite](#8-verification-suite)
9. [Troubleshooting](#9-troubleshooting)
10. [Operational cautions](#10-operational-cautions)

---

## 1. Prerequisites

| Software | Version | Needed for | Notes |
|---|---|---|---|
| Node.js | 22 or newer | The API | `node --version` |
| Python | 3.13 or newer | Inference, training, evaluation | `python --version` |
| 7-Zip | any | Preprocessing only | Expected at `C:\Program Files\7-Zip\7z.exe` |
| PostgreSQL | 15 | Optional | Without it the request log fails soft; detection is unaffected |

PostgreSQL is genuinely optional. `api/db/pool.js` fails soft when the database
is unreachable, so you lose the audit trail and nothing else.

---

## 2. First-time setup

From the repository root.

**Create the Python environment and install dependencies:**

```bash
python -m venv ml/venv
```

```bash
ml/venv/Scripts/python.exe -m pip install -r ml/requirements.txt
```

```bash
ml/venv/Scripts/python.exe -m pip install -r attack-sim/requirements.txt
```

**Install the API dependencies:**

```bash
cd api && npm install && cd ..
```

**Create your environment file:**

```bash
cp demo.env .env
```

### Trained models

`ml/models/` must contain `random_forest.pkl`, `xgboost.pkl`,
`isolation_forest.pkl`, `scaler.pkl` and `feature_order.json`. These are not in
version control — they are ~46 MB of build output.

If they are missing, either obtain them from whoever gave you the repository, or
build them yourself with the raw datasets in place (see section 7). The API will
start without them; the inference service will not report `ready`.

---

## 3. Starting the system

Two terminals, in this order.

**Terminal 1 — the inference service:**

```bash
cd ml && venv/Scripts/python.exe app.py
```

Wait for it to report ready. It loads ~46 MB of model artefacts, which takes a
few seconds. Do not skip this wait — the service answers HTTP while it is still
loading, so a check on the port alone will lie to you.

```bash
curl http://localhost:8000/health
```

Look for `"ready": true`, not just a 200 response.

**Terminal 2 — the API:**

```bash
cd api && node server.js
```

The API is now on <http://localhost:3000>.

### Stopping

`Ctrl+C` in each terminal. Nothing persists except the request log, if you have
PostgreSQL. Accounts are in-memory and reset on restart.

---

## 4. Checking it works

Three requests. The contrast between the second and third is the whole system.

**Is it alive:**

```bash
curl http://localhost:3000/health
```

**A normal search — allowed:**

```bash
curl "http://localhost:3000/api/search/vulnerable?q=laptop"
```

Returns search results.

**An injection attempt — blocked:**

```bash
curl "http://localhost:3000/api/search/vulnerable?q=%27%20UNION%20SELECT%20username%2C%20password%20FROM%20users%20--"
```

Returns HTTP 403 with `"error":"request blocked by threat detection"`, the
combined score, and the rules that fired.

**A normal login still works — the system is not simply blocking everything:**

```bash
curl -X POST http://localhost:3000/api/auth/register -H "Content-Type: application/json" -d "{\"username\":\"demo\",\"password\":\"demo-pass-123\"}"
```

```bash
curl -X POST http://localhost:3000/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"demo\",\"password\":\"demo-pass-123\"}"
```

The second returns a JWT. `api/test/endpoints.http` holds sample requests for
every endpoint if you prefer an HTTP client.

---

## 5. Configuration reference

Everything is environment-driven; no code change is needed to alter behaviour.

| Variable | Default | Effect |
|---|---|---|
| `DETECTION_MODE` | `hybrid` | `off`, `rules`, `hybrid` |
| `DETECTION_THRESHOLD` | `0.7` | Combined score at which a request is blocked |
| `COMBINE_STRATEGY` | `noisy_or` | `noisy_or`, `weighted`, `max`, `rules_only` |
| `ML_TIMEOUT_MS` | `250` | Inference timeout before falling back to rules |
| `ML_PAYLOAD_PATHS` | `/api/search` | Endpoint prefixes the classifier is consulted for |
| `DETECTION_TRACE` | `0` | `1` attaches per-request scores as response headers |
| `TRUST_PROXY` | `0` | `1` honours `X-Forwarded-For` — see section 10 |
| `PORT` | `3000` | API port |
| `ML_SERVICE_URL` | `http://localhost:8000` | Where the API looks for inference |
| `DATABASE_URL` | — | Unset means no request log; detection is unaffected |

### Two settings worth understanding

**`ML_PAYLOAD_PATHS`** scopes the classifier to endpoints that carry a payload.
This is not an optimisation. The payload model has signal on a search query and
none on a credential body, and applying it to `/api/auth/*` produced a 17.5%
false positive rate on ordinary logins. Widening this setting will reintroduce
that.

**`DETECTION_THRESHOLD`** cannot fix a false positive problem on its own. When
this was tried, the rate only became acceptable at 0.85, where ML recall
collapsed from 99% to 83%. Threshold changes trade recall for precision; they do
not create separation that is not there.

---

## 6. Running a demonstration

### The 60-second version

Start both services, then run the three curl commands in section 4. The allowed
search and the blocked injection against the same endpoint is the point.

### Showing the feature contract

```bash
ml/venv/Scripts/python.exe ml/demo_feature_extraction.py
```

Prints the 12 payload features for a benign string and for an injection payload
side by side. `laptop` scores entropy 2.25 with every injection flag at zero;
the injection payload scores entropy 4.48 with three flags set. This is what the
classifier sees — no keyword list involved.

### Proving the machine learning is actually engaged

Stop the inference service (Ctrl+C in terminal 1), leave the API running, and
send the injection payload again. It is now allowed: the API has degraded to its
rule stage, which is NFR2 working as designed. Restart inference and it blocks
again.

Nothing about the API changed. Only a separate process on a separate port
stopped. That is difficult to explain if the detection were hardcoded pattern
matching.

Turn on `DETECTION_TRACE=1` to see the rule score, ML score and combined score
as response headers on every request, allowed ones included.

### Generating attack traffic

Each generator writes a labelled CSV to `evaluation/traffic/`.

```bash
ml/venv/Scripts/python.exe attack-sim/benign_traffic.py
```

```bash
ml/venv/Scripts/python.exe attack-sim/sqli_attack.py
```

```bash
ml/venv/Scripts/python.exe attack-sim/brute_force.py
```

```bash
ml/venv/Scripts/python.exe attack-sim/credential_stuffing.py
```

Or all four in sequence:

```bash
ml/venv/Scripts/python.exe attack-sim/run_all.py
```

The behavioural generators need `TRUST_PROXY=1` so that simulated clients can
present distinct source addresses. Read section 10 before enabling it.

---

## 7. Regenerating the results

Steps 1 and 2 need the raw datasets in place — see `datasets/README.md` for the
expected layout. Everything after that needs only the trained models.

**1. Build the corpora** (~10 minutes; extracts the ATRDF archives on first run)

```bash
ml/venv/Scripts/python.exe ml/preprocess.py
```

Produces `datasets/processed/train.parquet` (677,166 rows) and
`heldout_atrdf.parquet` (540,057 rows).

**2. Train** (~15 minutes)

```bash
ml/venv/Scripts/python.exe ml/train.py
```

Writes the three models, the scaler, the feature order and a training summary
into `ml/models/`.

**3. Offline evaluation**

```bash
ml/venv/Scripts/python.exe ml/evaluate.py
```

Per-model metrics, the cross-dataset comparison, and four figures into
`evaluation/figures/`. Add `--no-figures` to skip plotting.

**4. Live comparison** — needs the traffic CSVs from section 6

```bash
ml/venv/Scripts/python.exe evaluation/compare_configs.py
```

**5. Results workbook**

```bash
ml/venv/Scripts/python.exe evaluation/build_workbook.py
```

Writes `evaluation/CB016639_Results_Workbook.xlsx` — eight sheets with native
editable charts.

Everything is seeded (`SEED=42`), so a rerun reproduces the same numbers.

---

## 8. Verification suite

Four checks. Run the first before trusting anything else.

**Feature contract parity — the NFR3 guarantee:**

```bash
cd api && npm test
```

Expect `240 comparisons, no divergence`. This proves the JavaScript and Python
halves of the feature contract compute identical vectors. If it fails, the
models are receiving inputs that do not mean what they were trained to mean —
and nothing will error, it will just be quietly wrong.

**End-to-end integration** (both services running):

```bash
node api/test/hybridIntegration.js
```

**The fail-open path** (inference service stopped):

```bash
node api/test/hybridIntegration.js --no-ml
```

**Inference service behaviour:**

```bash
ml/venv/Scripts/python.exe ml/test_inference.py
```

---

## 9. Troubleshooting

**The integration test exits with code 2 and complains about a dirty window.**

Working as intended. The behavioural features key on source address, and every
run uses the same one, so a second run inside 60 seconds starts with events
already in the window and the rate rules fire immediately. Wait 60 seconds or
restart the API.

**Benign requests are being blocked.**

Check `ML_PAYLOAD_PATHS` first — if it has been widened to include `/api/auth`,
that alone explains it (section 5). Otherwise check whether you have sent more
than 30 requests in the last minute: `RATE_ELEVATED` fires above that and adds
0.4 to every subsequent request's score. That is the rules working.

**The inference service returns 503, or `"ready": false`.**

The model artefacts are missing or failed to load. Check `ml/models/` against
the list in section 2, and read the service's own `/health` body — it names the
artefact that failed rather than just reporting a status.

**The API works but no requests are logged.**

`DATABASE_URL` is unset or PostgreSQL is unreachable. The write path fails soft
by design. Apply `db/init/01_schema.sql` if the table does not exist.

**Latency is around 250 ms instead of under 100 ms.**

The inference service is unreachable and every request is waiting out
`ML_TIMEOUT_MS` before falling back. That is the fail-open path behaving
correctly, not a performance defect.

**Preprocessing fails on ATRDF.**

It shells out to 7-Zip at `C:\Program Files\7-Zip\7z.exe`. Install 7-Zip, or
extract the `.7z` archives yourself into sibling directories of the same name.

---

## 10. Operational cautions

Three things to know before running this anywhere that matters.

**`TRUST_PROXY=1` is unsafe outside the test harness.** It makes the framework
believe a client-supplied `X-Forwarded-For` header. An attacker who can set that
header can present a fresh source address on every request and defeat every
behavioural rule in the system. It exists so the simulation can generate traffic
from distinct sources on one machine. It is off by default and warns loudly when
enabled. Leave it off.

**This is a single-node control.** The sliding window lives in process memory.
Running several API instances behind a load balancer would divide each
attacker's traffic between them, and no single instance would accumulate the
evidence its behavioural rules need. Fixing this means an external shared store
such as a Redis sorted set keyed by source.

**Do not assume these results transfer.** Every performance figure in this
repository describes traffic resembling the training corpus. On a corpus from a
different source, ROC-AUC falls from 0.9731 to 0.5254 and the system blocks 72%
of benign traffic. Before deploying into a new environment, measure on traffic
from that environment. The cause is understood — covariate shift, diagnosed in
`evaluation/results.md` — but it is not fixed in this release.
