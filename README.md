# Intelligent Threat Detection and Prevention in REST APIs Using Machine Learning

MSc Cyber Security dissertation artefact (CB016639). A hybrid rule-based and
machine-learning detection framework for REST APIs, targeting SQL injection,
brute force and credential stuffing in real time.

The framework runs as middleware ahead of every API route. Each request is
reduced to 17 numeric features, judged by a 15-rule signature engine and by
three trained models, and the two verdicts are combined into one decision.

---

## Status

**Implementation complete.** All ten build phases are finished; measured
results are in [`evaluation/results.md`](evaluation/results.md).

| Phase | Area | Status |
|---|---|---|
| 0 | Environment and scaffold | Complete |
| 1 | Dataset preprocessing, feature contract | Complete |
| 2 | REST API | Complete |
| 3 | Rule-based detection middleware | Complete |
| 4 | Model training | Complete |
| 5 | Inference service and combined scoring | Complete |
| 6 | Hybrid integration | Complete |
| 7 | Docker Compose runtime | Complete |
| 8 | Attack simulation and threshold recalibration | Complete |
| 9 | Comparative evaluation | Complete |
| 10 | Documentation and reproducibility | Complete |

### Headline results

On 217 labelled requests generated against the running system:

| Configuration | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|
| No detection | 0.5576 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Rules only | 0.9032 | 0.9747 | 0.8021 | 0.8800 | 0.0165 |
| ML only | 0.5853 | 0.6667 | 0.1250 | 0.2105 | 0.0496 |
| ModSecurity (OWASP CRS) | 0.6636 | 1.0000 | 0.2396 | 0.3866 | 0.0000 |
| **Hybrid (proposed)** | **0.9447** | 0.9565 | **0.9167** | **0.9362** | 0.0331 |

The hybrid is significantly better than every baseline (McNemar exact test,
p < 0.05 against all four). The mechanism is complementary failure: the rule
engine catches tautology and union injection perfectly and misses comment and
stacked injection entirely, while the classifier does the opposite. On blind
and obfuscated injection neither component exceeds 67% and the hybrid reaches
100%.

**Two findings are negative and are reported as prominently as the positive
ones:**

- The trained models **do not generalise** to the held-out ATRDF 2023 corpus
  (ROC-AUC 0.9731 on the internal test split, **0.5254** on ATRDF — random).
  Four experiments establish the cause as covariate shift rather than an
  inadequate feature set. See `results.md` §9.2.
- ModSecurity achieves **perfect precision and a 0.0% false positive rate**,
  better than this framework on both counts. The hybrid's advantage comes from
  covering behavioural attacks the WAF does not attempt, not from being better
  at injection detection.

---

## Architecture

```
                        ┌──────────────────────────────────────────┐
   HTTP request ───────►│  api  (Node.js 22 + Express)             │
                        │                                          │
                        │  detection middleware, ahead of routes    │
                        │  ┌────────────────────────────────────┐  │
                        │  │ 1. extract 17 features             │  │
                        │  │    12 payload + 5 behavioural      │  │
                        │  ├────────────────────────────────────┤  │
                        │  │ 2. rule engine — 15 signatures     │  │
                        │  ├────────────────────────────────────┤  │
                        │  │ 3. high-severity rule? ──► block   │  │
                        │  │    (short-circuit, no ML call)     │  │
                        │  ├────────────────────────────────────┤  │
                        │  │ 4. else score via ml service ──────┼──┼──► ml
                        │  ├────────────────────────────────────┤  │   (FastAPI)
                        │  │ 5. combine (noisy-OR), threshold   │  │   RF + XGBoost
                        │  │    0.70 ──► allow / block (403)    │  │   + IsolationForest
                        │  └────────────────────────────────────┘  │
                        └──────────────┬───────────────────────────┘
                                       │ every decision + feature vector
                                       ▼
                                 db (PostgreSQL 15)
                                 request_log, JSONB features
```

**Fail-open (NFR2):** if the inference service is unreachable or exceeds
`ML_TIMEOUT_MS`, the request is judged on the rule verdict alone and the outage
is logged. Detection degrades; availability does not.

| Directory | Contents |
|---|---|
| `api/` | Express API, detection middleware, rule engine, feature extractor (JS), tests |
| `ml/` | Feature contract (Python), preprocessing, training, inference service, evaluation |
| `attack-sim/` | Traffic generators and threshold recalibration |
| `evaluation/` | Results, figures, workbook, configuration comparison |
| `datasets/` | Raw and processed corpora (gitignored — see `datasets/README.md`) |
| `db/` | Schema, applied on first volume initialisation |

---

## Environment

Developed on Windows 11 with Node.js 22 and Python 3.13 (functionally
equivalent to the Node 20 / Python 3.11 in the build specification). Both
services ship as Linux containers (`node:22-slim`, `python:3.13-slim`), so the
deployed artefact is Linux-based regardless of host OS.

---

## Running the stack

### With Docker (recommended)

```bash
cp demo.env .env
docker compose up --build
```

PostgreSQL, the inference service and the API start in that order — the API
waits for both dependencies to report healthy, so a request never reaches a
service still loading. The API is then on <http://localhost:3000>.

For a step-by-step walkthrough written for someone with no prior context, see
[`QUICKSTART.md`](QUICKSTART.md).

### Without Docker

Two terminals. First the inference service:

```bash
cd ml && venv/Scripts/python.exe app.py
```

Wait for `"ready": true` at <http://localhost:8000/health> — it loads ~46 MB of
models. Then the API:

```bash
cd api && node server.js
```

### Prerequisite: trained models

`ml/models/` must contain `random_forest.pkl`, `xgboost.pkl`,
`isolation_forest.pkl`, `scaler.pkl` and `feature_order.json`. They are
bind-mounted rather than baked into the image, and are not in version control.
See *Reproducing the results* below to generate them.

### Configuration

Behaviour is environment-driven, which is how the Phase 9 evaluation builds its
comparison configurations without code changes:

| Variable | Default | Effect |
|---|---|---|
| `DETECTION_MODE` | `hybrid` | `off`, `rules`, `hybrid` |
| `DETECTION_THRESHOLD` | `0.7` | Combined score at which a request is blocked |
| `COMBINE_STRATEGY` | `noisy_or` | `noisy_or`, `weighted`, `max`, `rules_only` |
| `ML_TIMEOUT_MS` | `250` | Inference timeout before falling back to rules |
| `DETECTION_TRACE` | `0` | `1` attaches per-request scores as response headers |
| `TRUST_PROXY` | `0` | `1` honours `X-Forwarded-For`; required by the traffic harness, unsafe otherwise |

---

## Reproducing the results

Every figure and table in the dissertation regenerates from this repository.
Steps 1 and 2 need the raw datasets in place (`datasets/README.md`); steps 3
onward need only the trained models.

**1. Environment**

```bash
python -m venv ml/venv
ml/venv/Scripts/python.exe -m pip install -r ml/requirements.txt
ml/venv/Scripts/python.exe -m pip install -r attack-sim/requirements.txt
cd api && npm install && cd ..
```

**2. Build the corpora and train** *(~4 minutes)*

```bash
ml/venv/Scripts/python.exe ml/preprocess.py
ml/venv/Scripts/python.exe ml/train.py
```

Produces `datasets/processed/train.parquet` (677,166 rows) and
`heldout_atrdf.parquet` (540,057 rows, never trained on), then writes the model
artefacts. Training is seeded (`SEED = 42`) and reproduces identical figures.

**3. Verify the feature contract**

```bash
cd api && npm test && cd ..
```

Compares the JavaScript and Python feature extractors across 20 payloads and 12
features. Must report 240 comparisons with no divergence — if the two halves
diverge, the models receive inputs that do not mean what they were trained on.

**4. Offline evaluation and cross-dataset generalisation** *(~1 minute)*

```bash
ml/venv/Scripts/python.exe ml/evaluate.py
```

Writes `evaluation/phase9_offline.json` and four figures: ROC curves, confusion
matrices, feature importance, generalisation drop.

**5. Generate labelled traffic** *(stack must be running with `TRUST_PROXY=1`
and `DETECTION_TRACE=1`)*

```bash
ml/venv/Scripts/python.exe attack-sim/benign_traffic.py
ml/venv/Scripts/python.exe attack-sim/sqli_attack.py
ml/venv/Scripts/python.exe attack-sim/brute_force.py
ml/venv/Scripts/python.exe attack-sim/credential_stuffing.py
```

Restart the API between generators to clear the 60-second behavioural window,
or each will be judged partly on traffic the previous one sent. Each generator
refuses to start against a dirty window rather than producing quietly wrong
numbers.

**6. Comparative evaluation and workbook**

```bash
ml/venv/Scripts/python.exe evaluation/compare_configs.py
ml/venv/Scripts/python.exe evaluation/build_workbook.py
```

Produces the configuration comparison, McNemar significance tests, per-attack
breakdown, latency analysis, and `CB016639_Results_Workbook.xlsx` — eight
sheets with six native, editable Excel charts.

**Optional — ModSecurity baseline.** Run the API with `DETECTION_MODE=off`,
then:

```bash
docker run -d --name modsec-baseline -p 8080:8080 \
  -e BACKEND="http://host.docker.internal:3000" -e PORT=8080 \
  -e MODSEC_RULE_ENGINE=On -e PARANOIA=1 -e ANOMALY_INBOUND=5 \
  owasp/modsecurity-crs:nginx
```

Re-run the generators with `API_URL=http://localhost:8080 --allow-dirty-window`,
move the output to `evaluation/traffic_modsec/`, and `compare_configs.py` picks
it up automatically as a fifth configuration.

---

## Verification

```bash
cd api && npm test                       # feature parity, 240 comparisons
node api/test/hybridIntegration.js       # end to end; --no-ml for the fail-open path
ml/venv/Scripts/python.exe ml/test_inference.py
```

`api/test/endpoints.http` holds sample requests for every endpoint.
Authentication is in-memory and resets on restart; `api/db/pool.js` writes to
`request_log` when Postgres is available and fails soft when it is not.

---

## Documentation

| File | Purpose |
|---|---|
| [`evaluation/results.md`](evaluation/results.md) | All measured results, phase by phase |
| [`docs/deployment-aws-feasibility.md`](docs/deployment-aws-feasibility.md) | How this would deploy to AWS, and why it did not |
| [`QUICKSTART.md`](QUICKSTART.md) | Assumption-free setup for a new machine |
| `evaluation/CB016639_Results_Workbook.xlsx` | Results as native Excel tables and charts |
| `evaluation/figures/` | Generated figures |

---

## Ethics

All attack traffic is generated by this project's own scripts against this
project's own local API. No external or third-party system is contacted at any
point.

- The `/api/search/vulnerable` endpoint constructs an unsanitised query by
  string concatenation and returns it for inspection, but **never executes it**.
  There is no exploitable database behind it.
- Credential-stuffing pairs are **synthetic**, generated from a fixed seed. No
  real breached credentials were obtained, stored or used.
- All datasets are publicly available research datasets used under their
  licences. ATRDF 2023 is held out and never trained on.
- No real malware and no real user data are involved.
- `TRUST_PROXY=1`, required by the traffic harness so simulated clients present
  distinct sources, is off by default and warns loudly when enabled — trusting a
  client-supplied source header would let an attacker defeat every behavioural
  rule.
