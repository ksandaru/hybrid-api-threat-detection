# Release Notes

## v1.0.0 — 10 September 2026

First complete release. The framework is feature-complete, measured, and
reproducible from a clean checkout. Everything below is implemented and
verified; nothing is stubbed.

### What this release contains

A hybrid rule-based and machine-learning threat detection framework for REST
APIs, running as Express middleware ahead of every route. Each request is
reduced to 17 numeric features, judged by a 15-rule signature engine and by an
ensemble of three trained models, and the two verdicts combined into one
decision.

| Component | What it does |
|---|---|
| `api/` | Node.js 22 + Express REST API with the detection middleware |
| `ml/` | Python 3.13 + FastAPI inference service, training and evaluation |
| `attack-sim/` | Four traffic generators, all against our own local API |
| `evaluation/` | Comparative evaluation, results workbook, figures |
| `db/` | PostgreSQL schema for the request log |

### Measured results

On 217 labelled requests generated against the running system:

| Configuration | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|
| No detection | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Rules only | 0.9747 | 0.8021 | 0.8800 | 0.0165 |
| ML classifier only | 0.6667 | 0.1250 | 0.2105 | 0.0496 |
| ModSecurity v3 + OWASP CRS | 1.0000 | 0.2396 | 0.3866 | 0.0000 |
| **Hybrid (proposed)** | 0.9565 | **0.9167** | **0.9362** | 0.0331 |

The hybrid beats every baseline significantly (McNemar exact test, p < 0.05
against all four; p = 0.022 against rules-only). Added latency is 90.28 ms at
the 95th percentile on the inference path, inside the 100 ms budget, and
3.98 ms median on the rule short-circuit path.

### Two negative findings, reported as prominently as the positive ones

**The models do not generalise.** ROC-AUC is 0.9731 on the internal test split
and 0.5254 on the held-out ATRDF 2023 corpus — indistinguishable from random.
Four controlled experiments identify covariate shift rather than an inadequate
feature set: the most important feature is constant at zero across the held-out
corpus, and the most important payload feature sits beyond 2σ of the training
distribution for 98.7% of its rows.

**ModSecurity has better precision than we do.** The OWASP Core Rule Set
achieved precision 1.0000 and a false positive rate of 0.0000 on this traffic,
better than this framework on both. Its low F1 comes entirely from recall: it
does not attempt behavioural detection. The hybrid's advantage is coverage of an
attack class the firewall does not try to cover, not better injection detection.

---

## Changes in this release

### Added

- `USER_MANUAL.md` — operator guide for running, configuring and demonstrating
  the system natively, without Docker.
- `RELEASE_NOTES.md` — this file.
- `legacy/` — retired material with a README explaining what moved and why.
- Documentation for `api/test/featureParity.js` and
  `ml/demo_feature_extraction.py`, which were previously undocumented despite
  being the clearest evidence for NFR3 and for the feature contract.

### Changed

- Comments across the source were shortened. The rationale that belongs in the
  research record now lives in `evaluation/results.md`; comments carry only what
  a reader of the code needs.
- Internal build vocabulary ("Phase 5", "Phase 9") removed from code, schema,
  Compose file and READMEs — it meant nothing outside the build spec.
  `evaluation/results.md` keeps it, because it is the dated research log.
- `api/package.json` version 0.1.0 → 1.0.0.
- `.gitignore` excludes `legacy/dataset-archives/`.

### Moved to `legacy/`

545 MB of superseded material, none of it referenced by source, README or
`docker-compose.yml`. See [`legacy/README.md`](legacy/README.md).

- The development demonstration deck
- An empty exploration notebook
- Redundant dataset archives: the 442 MB corpus bundle, the Kaggle download zip
  and its two superseded CSV versions, the ECML CSIC variant, and the upstream
  CSIC distribution whose flattened form the pipeline actually reads

Deliberately **not** moved: the ATRDF `.7z` archives (`ml/preprocess.py`
extracts them on demand), every direct pipeline input, the ModSecurity
comparison traffic, and the Docker artefacts.

---

## Known limitations

These are measured, not suspected. Each is documented with its consequence.

| Limitation | Consequence |
|---|---|
| The models do not transfer across corpora | Every performance figure describes traffic resembling the training corpus. Measure on target traffic before deploying anywhere new. |
| Four of five behavioural features carry zero model importance | The ML element is demonstrated for injection only. Brute force and credential stuffing are detected by the rule stage. |
| The sliding window is held in process memory | Single-node control. Scaling horizontally would split each attacker's traffic across instances and break behavioural detection. |
| No credential-stuffing examples in the offline corpus | No public corpus of genuine credential stuffing exists; brute force flows stand in as behavioural proxies. |
| Latency measured single-client | Not a load test. Behaviour under concurrency is not established. |
| `TRUST_PROXY=1` trusts a client-supplied source header | Off by default and warns when enabled. Required only by the traffic harness. Never enable it in production. |

## Upgrade notes

None — this is the first release.

## Verifying this release

```bash
cd api && npm test
```

Expect `PASS  20 payloads x 12 features = 240 comparisons, no divergence`. That
is the NFR3 guarantee: the JavaScript and Python halves of the feature contract
agree exactly. If it fails, the models are being fed inputs that do not mean
what they were trained to mean, and no other result in this repository can be
trusted until it passes again.
