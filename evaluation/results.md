# Evaluation Results

This file accumulates results across phases: dataset statistics (Phase 1),
per-model training metrics (Phase 4), the inference service and combined
scoring (Phase 5), hybrid integration (Phase 6), and the full comparative
evaluation (Phase 9). See `docs/phase-N-*/` for the what/why/how narrative behind each
section below.

## Phase 1 — Dataset Statistics

Produced by `ml/preprocess.py`, unifying four public research datasets into
a shared 17-feature schema (`ml/features.py`). See
`docs/phase-1-datasets/IMPLEMENTATION.md` for full acquisition and
cleaning detail, and `docs/phase-1-datasets/MEMORY.md` for documented
limitations (CICIDS2017 flow-feature proxy gaps, CSIC's multi-attack-type
"Anomalous" class, no credential-stuffing examples in the offline corpus).

### Training corpus (`datasets/processed/train.parquet`)

Shape: **677,166 rows × 20 columns** (17 canonical features + `label` +
`attack_type` + `source`).

| Source | Benign (0) | Attack (1) | Total | Notes |
|---|---:|---:|---:|---|
| Kaggle SQLiV3 | 19,268 | 11,341 | 30,609 | Payload strings; ~1% of raw rows dropped (comma-corrupted Label values) |
| CSIC 2010 | 36,000 | 25,065 | 61,065 | Reconstructed request text from URI + GET-Query + POST-Data |
| CICIDS2017 (Tuesday) | 412,692 | 9,152 | 421,844 | FTP-Patator + SSH-Patator brute force |
| CICIDS2017 (Thursday AM) | 162,157 | 1,491 | 163,648 | Web Attack Brute Force + SQL Injection only (XSS excluded — out of scope) |
| **Total** | **630,117** | **47,049** | **677,166** | |

Attack-type breakdown: `none` 630,117 · `sqli` 36,427 (Kaggle + CSIC + CICIDS
Thursday SQLi) · `brute_force` 10,622 (CICIDS Tuesday + Thursday Patator/web
brute force).

Overall class imbalance (benign : attack) ≈ **13.4 : 1** — SMOTE will be
applied to the training split only, in Phase 4, per the spec.

**No `credential_stuffing` examples exist in this offline corpus** — none
of the four source datasets contain genuine credential-stuffing traffic
(replayed leaked credential pairs). This attack type will only appear as
labelled traffic once Phase 8's synthetic `credential_stuffing.py`
generator is run against the live API; it is not part of the Phase 1/4
offline training set. This is a limitation to state explicitly in the
dissertation, not an oversight.

### Held-out corpus (`datasets/processed/heldout_atrdf.parquet`)

Shape: **540,057 rows × 20 columns**. Built from all 4 ATRDF 2023 difficulty
levels (train + val splits each), extracted from `.7z` archives.
**Never used in training** — reserved exclusively for the Phase 9
cross-dataset generalisation test.

| ATRDF dataset | Benign (0) | Attack (1) | Total |
|---|---:|---:|---:|
| dataset_1 | 2,773 | 2,264 | 5,037 |
| dataset_2 | 140,414 | 9,586 | 149,999 |
| dataset_3 | 153,884 | 16,116 | 170,000 |
| dataset_4 | 175,684 | 39,336 | 215,020 |
| **Total** | **472,755** | **67,302** | **540,057** |

Attack-type breakdown: `none` 472,755 · `sqli` 13,974 (maps directly to this
project's SQLi class) · `other` 53,328 (ATRDF's Cookie Injection, LOG4J,
Log Forging, Directory Traversal, RCE — attack types outside this
project's three-attack scope, kept in the held-out set for label=1/label=0
binary generalisation testing, but not part of any attack-type-specific
metric).

Held-out class imbalance (benign : attack) ≈ **7.0 : 1**.

### Known feature-engineering limitations (carried into Phase 4/9 analysis)

1. **CICIDS2017's standard "MachineLearningCSV" format has no Source IP or
   Timestamp columns.** Of the 5 flow-level features, only
   `inter_arrival_time_variance` is genuinely derived (from the dataset's
   own `Flow IAT Std` column, squared). `requests_per_min_ip`,
   `distinct_usernames_tried`, and `unique_ip_count_window` are zero-filled
   for every CICIDS row — real values only exist at live inference time via
   the Phase 3 Express middleware's per-IP sliding window.
2. **`login_failure_ratio` is zero-filled everywhere in the offline
   corpus** — none of the four sources carry application-layer
   login-success/failure signal. This is purely a live-inference feature.
3. **Payload features are zero-filled for all CICIDS rows** (network flow
   data has no request text), and **flow features are zero-filled for all
   Kaggle/CSIC/ATRDF rows** (single-request payload sources, no sliding
   window). Each training row therefore has a genuinely informative value
   in only one of the two feature families — this is expected and by
   design, not a data quality bug.

## Phase 4 — Model Training Metrics

Produced by `ml/train.py` on the unified corpus (677,166 rows, 17 features).
Reproduce with `.\ml\venv\Scripts\python ml\train.py`; seeded at 42 throughout.

### Procedure

A three-way stratified split: 460,472 train, 81,260 validation, 135,434 test.
`StandardScaler` is fitted on the training split only; SMOTE is applied to the
training split only and only after the split, raising it to 856,878 balanced
rows. Cross-validation runs SMOTE **inside** each fold through an
imbalanced-learn pipeline, so no synthetic sample derived from a validation row
reaches that fold's training data.

The validation split exists so that the decision threshold reported in Phase 5
can be chosen on data the models never fitted, without touching the test split.
Selecting an operating point on the test split would make the test metrics
optimistic, because the threshold would have been tuned to them.

### Individual models, held-out test split (135,434 rows)

| Model | Accuracy | Precision | Recall | F1 | FPR | ROC AUC |
|---|---:|---:|---:|---:|---:|---:|
| Random Forest | 0.9650 | 0.6912 | 0.8962 | 0.7804 | 0.0299 | 0.9591 |
| XGBoost | 0.9556 | 0.6225 | 0.9188 | 0.7422 | 0.0416 | 0.9763 |
| Isolation Forest | 0.9156 | 0.4345 | 0.7123 | 0.5398 | 0.0692 | 0.8977 |

Isolation Forest is unsupervised and fitted on benign training rows only. Its
weaker precision is expected and is the accepted cost of detecting attack shapes
absent from the training labels.

### Stratified 5-fold cross-validation (training split)

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
|---|---:|---:|---:|---:|---:|
| Random Forest | 0.9650 ± 0.0004 | 0.6912 ± 0.0033 | 0.8963 ± 0.0018 | 0.7805 ± 0.0021 | 0.9613 ± 0.0010 |
| XGBoost | 0.9545 ± 0.0035 | 0.6161 ± 0.0216 | 0.9228 ± 0.0054 | 0.7386 ± 0.0138 | 0.9769 ± 0.0005 |

Cross-validated figures sit within 0.001 of the single held-out split, with
fold-to-fold deviation of 0.0004 for Random Forest. The reported performance is
a property of the corpus rather than of one fortunate partition. No model
approaches perfect accuracy, which is the intended outcome: the methodology
states in advance that a near-perfect score would be treated as evidence of
leakage rather than as success.

### Per-source performance (XGBoost, test split)

| Source | Rows | Attacks | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kaggle SQLiV3 | 6,079 | 2,204 | 0.8923 | 0.7726 | 0.9959 | 0.8702 | 0.1667 |
| CSIC 2010 | 12,281 | 5,023 | 0.8561 | 0.7445 | 0.9869 | 0.8487 | 0.2344 |
| CICIDS2017 (Tuesday) | 84,344 | 1,863 | 0.9686 | 0.3882 | 0.7332 | 0.5076 | 0.0261 |
| CICIDS2017 (Thursday) | 32,730 | 320 | 0.9714 | 0.1470 | 0.4000 | 0.2149 | 0.0229 |

The aggregate conceals a split down the middle of the corpus. On the two
payload-level sources the classifier recalls 99.6% and 98.7% of attacks; on the
two flow-level sources it recalls 73.3% and 40.0%. Because the CICIDS rows are
86% of the corpus and 97.5% benign, they pull aggregate accuracy up while
contributing most of the missed attacks.

### Feature importances

| Rank | Random Forest | | XGBoost | |
|---|---|---:|---|---:|
| 1 | inter_arrival_time_variance | 0.2869 | inter_arrival_time_variance | 0.3235 |
| 2 | payload_length | 0.2651 | payload_length | 0.2133 |
| 3 | shannon_entropy | 0.1820 | shannon_entropy | 0.1325 |
| 4 | special_char_ratio | 0.1325 | has_comment | 0.0687 |
| 5 | equals_count | 0.0803 | double_dash_count | 0.0667 |
| 6 | sql_keyword_count | 0.0186 | sql_keyword_count | 0.0642 |

### Four features carry zero importance in both models

Both classifiers assign **exactly zero** importance to `requests_per_min_ip`,
`login_failure_ratio`, `distinct_usernames_tried` and `unique_ip_count_window`.

These are the four flow features zero-filled throughout the offline corpus, for
the reasons recorded in the Phase 1 statistics: the CICIDS2017 distribution
format carries neither source addresses nor timestamps, and the payload-level
sources are single requests with no window to compute them over. A constant
column carries no information and the models correctly ignore it.

The consequence is material. **The trained classifiers cannot detect brute force
or credential stuffing**, because the only features that would express those
attacks are the ones they learned to disregard. The single flow feature that
does carry signal, `inter_arrival_time_variance`, ranks first in both models,
which is why the CICIDS rows are classified at all.

Detection of the two behavioural attack categories therefore rests entirely on
the rule engine, which computes all five flow features live from the sliding
window. This does not weaken the argument for a hybrid design, it sharpens it:
for two of the three target attacks the rule stage is not a cheap pre-filter
ahead of the classifier, it is the only stage carrying signal.

### Inference cost per model (single request, 200 timed calls after warm-up)

| Model | p50 | p95 | p99 | Artefact | Load |
|---|---:|---:|---:|---:|---:|
| Random Forest | 16.01 ms | 26.04 ms | 27.28 ms | 230 MB | 1.77 s |
| XGBoost | 0.26 ms | 0.57 ms | 0.92 ms | 279 KB | 0.03 s |
| Isolation Forest | 5.11 ms | 6.60 ms | 7.27 ms | 500 KB | 0.03 s |

Random Forest costs roughly sixty times more per prediction than XGBoost while
scoring lower on ROC AUC, and its trees are grown without depth constraint on
the resampled training set, which is what produces the 230 MB artefact. That
size was later tested directly rather than assumed to be waste - see
"Model size: a constraint that was measured, not assumed" below.

## Phase 5 — Inference Service and Combined Scoring

`ml/app.py` loads the artefacts once at startup and exposes `/health`, `/meta`
and `/predict`. The score is a weighted combination of the three models:

    score = 0.4 · P_rf(attack) + 0.4 · P_xgb(attack) + 0.2 · normalised_iso

Random Forest and XGBoost emit probabilities directly. Isolation Forest emits an
unbounded anomaly score, mapped onto [0, 1] using the 1st and 99th percentiles of
its training-split score distribution (p1 = 0.2988, p99 = 0.7704), recorded by
`ml/train.py`. Percentiles rather than min and max, so a single extreme row
cannot compress the scale. Without that mapping the third term would silently
dominate or vanish depending on the range the forest happened to produce.

The service reads its weights and threshold from the saved artefact rather than
keeping its own copy, so the scoring it performs cannot drift from the scoring
the operating point was measured against.

### Operating point

The threshold was selected on the **validation split**, restricted to
payload-bearing sources, by maximising F1 over a grid from 0.05 to 0.95:

| | Threshold | Recall | FPR | F1 |
|---|---:|---:|---:|---:|
| Maximum F1 (selected) | 0.77 | 0.9595 | 0.0541 | 0.9398 |
| Constrained to FPR ≤ 5% | 0.78 | 0.9490 | 0.0470 | — |

Restricting selection to payload-bearing rows is deliberate. The flow-only
sources are 86% of the corpus, carry no request text and are 97.5% benign, so a
threshold fitted to the aggregate is dominated by traffic that does not resemble
an HTTP API request. A deployed service sees requests.

### Combined pipeline on the untouched test split, at threshold 0.77

| Population | Accuracy | Precision | Recall | F1 | FPR | ROC AUC |
|---|---:|---:|---:|---:|---:|---:|
| All test rows | 0.9790 | 0.8743 | 0.8145 | 0.8433 | 0.0087 | 0.9731 |
| Payload-bearing rows only | 0.9480 | 0.9128 | 0.9597 | 0.9357 | 0.0596 | 0.9840 |

The combination outperforms every individual model: F1 rises from 0.7804 (the
best single model) to 0.8433 overall, and ROC AUC from 0.9763 to 0.9840 on
payload traffic. Validation FPR of 0.0541 against test FPR of 0.0596 indicates
the selected threshold transferred rather than fitting the validation split.

### Why the aggregate false positive rate overstates deployment performance

At the same threshold the combined pipeline reports an FPR of 0.87% across all
test rows but 5.96% on payload-bearing rows alone. The lower figure is an
artefact of composition: 86% of the corpus consists of network flow records with
every payload feature zero-filled, which no live HTTP request resembles. The
figure a practitioner should read is the payload-only one.

This is a property of the available data rather than of the framework. No public
dataset covers all three target attacks in REST API format, so the corpus was
necessarily assembled from sources with different shapes. It is recorded here
because reporting the aggregate alone would materially overstate how the system
behaves in deployment.

### Service-level verification

`ml/test_inference.py` samples 300 benign and 300 attack rows from the corpus,
sends each through the running service, and confirms the service reproduces the
offline measurement: FPR 0.027, recall 0.983, mean score separation 0.688. It
also checks that a partial feature object is reported as such rather than
silently scored, since a mistyped feature name would otherwise return a
plausible but meaningless prediction.

Hand-constructed requests shaped the way the Express middleware builds them are
reported alongside, without assertion. Two observations from them are worth
carrying into Phase 8, where realistic benign traffic is generated:

- Some plainly benign requests score above the threshold (a login request
  scores 0.837), while some genuine SQL injection scores below it (a stacked
  query scores 0.311). Investigation confirmed these are borderline rather than
  systematic: real benign rows in the same feature neighbourhood have a median
  score of 0.386, and the pipeline flags only 3.5% of real benign payload rows.
- The behavioural vectors score 0.027, confirming the Phase 4 finding directly
  at the service boundary rather than only in feature importances.

## Phase 6 — Hybrid Integration

The rule stage and the inference service are joined in
`api/middleware/detection.js`, with the combination logic isolated in
`api/middleware/scoreCombiner.js`. Verified by `api/test/hybridIntegration.js`,
run once with the inference service up and once with it stopped.

### Why the combination is not a weighted mean

The specification suggests combining the two scores as a weighted mean. Phases 4
and 5 measured why that fails here. The classifiers assign zero importance to
four of the five flow features, so a brute-force vector scores 0.027 at the
inference service. Under a weighted mean, a rule engine 0.90 confident of a
brute-force attack would produce

    0.5 × 0.90 + 0.5 × 0.027 = 0.46

which is below the 0.7 block threshold. The ML term would not merely fail to
help, it would cancel a correct detection, making the hybrid detect *less* than
rules alone on two of the three target attacks.

The default is a noisy-OR, the standard combination for independent evidence:

    combined = 1 − (1 − rule) × (1 − ml)

It is never below either input, so neither stage can cancel the other, and
corroboration is rewarded: 0.5 and 0.5 combine to 0.75. Weighted mean, maximum
and rules-only are also implemented and selectable via `COMBINE_STRATEGY`,
because comparing them is a Phase 9 result rather than a decision to settle by
argument.

### A scale mismatch that had to be fixed first

Combining the two scores raw was wrong. The rule score accumulates evidence
weights; the ML score is a blend of three model outputs whose decision boundary
was fitted on the validation split and sits at **0.77**, not 0.5. Feeding a raw
ML score of 0.79 into a noisy-OR reads it as "79% confident" when it means
"just over the line" — and because a noisy-OR never reduces a score, that alone
cleared the 0.7 threshold and rejected legitimate traffic.

The ML score is now mapped piecewise so its own boundary lands at 0.5: below the
boundary compresses into [0, 0.5], above it into [0.5, 1]. A marginal verdict
contributes marginal evidence. The boundary is discovered from the service's
`/meta` endpoint rather than hard-coded, so the two cannot drift apart.

Effect on the observed cases:

| Case | Rule | ML raw | ML aligned | Combined | Blocks at 0.7 |
|---|---:|---:|---:|---:|---|
| Benign search | 0.00 | 0.790 | 0.543 | 0.543 | no |
| Benign login | 0.00 | 0.837 | 0.646 | 0.646 | no |
| Attack the rules miss | 0.50 | 0.996 | 0.991 | 0.996 | yes |
| High-confidence ML | 0.00 | 0.990 | 0.978 | 0.978 | yes |

### Results

Both configurations pass all checks. The comparison between them is the result.

| | Inference up (hybrid) | Inference down (rules only) |
|---|---|---|
| Added latency, p50 | 47.7 ms | 6.1 ms |
| Added latency, p95 | 51.3 ms | 9.0 ms |
| Benign false positive rate | **33.3%** (2 of 6) | **0.0%** (0 of 6) |
| Rule-catchable attacks | all blocked | all blocked |
| Attack the rules miss | **blocked at 0.96** | allowed |
| Brute force | blocked | blocked from attempt 5 |

The headline deliverable is met: `admin'-- DROP TABLE` scores 0.500 on rules
alone, below the threshold, and is allowed. With the classifier consulted it
scores 0.96 and is blocked. That is an attack the rules miss and the ML stage
catches, which is the case the hybrid design exists to handle.

Fail-open is met: with the inference service stopped, the API continues serving,
rule-catchable attacks are still blocked, and only the ML-dependent detection is
lost. A refused connection is detected in about 3 ms rather than waiting out the
250 ms timeout, so the degraded path costs almost nothing. One warning is logged
per outage and then every tenth failure, so an outage is visible without
flooding the log.

Behavioural detection is not weakened. A high-severity rule short-circuits before
the inference call is made, so brute force and credential stuffing never reach
the combination step and cannot be diluted by a near-zero ML score. This is the
cascade design doing exactly what Section 2.3 describes, and it is also why the
hybrid path costs nothing extra on the attacks it already catches: the union
select case completes in 1.2 ms because the classifier is never consulted.

### The cost: false positives

The hybrid blocked 2 of 6 benign requests where rules alone blocked none. Both
were ML false positives, not rule failures:

- `usb-c hub` scored 0.816 combined
- a valid login with an 18-character username scored 0.783

The second is diagnostic rather than incidental. `payload_length` is the
classifier's second most important feature, and the corpus associates length
with attacks, so a login with a longer username scores higher purely because the
request is longer. A short username passes where a long one does not. The model
is using length as a proxy for maliciousness rather than reading the request.

This traces directly to the corpus limitation recorded in Phase 5: 86% of the
training rows are network flow records that resemble no HTTP request, and the
payload-bearing rows that remain are 40% attacks, so any request carrying text
starts from a high prior. The benign traffic in the corpus does not cover the
shape of this API's own benign traffic.

**The hybrid is therefore not yet deployable at this operating point.** Trading a
33% false positive rate for one additional detected attack class is not a
favourable exchange for an inline control. What is missing is representative
benign traffic to calibrate against, which Phase 8 generates. The threshold
should be re-selected on that traffic before the Phase 9 comparison is run, and
the comparison should report the rule-only and hybrid false positive rates side
by side rather than accuracy alone.

### Latency

The classifier adds roughly 41 ms at the median (47.7 ms against 6.1 ms), which
is inside the 100 ms budget but is dominated by the Random Forest at about 16 ms
per prediction. Requests rejected by a high-severity rule bypass the call
entirely and complete in 1–3 ms. The measurement here is a single client on one
machine and is not a load test; Phase 9 measures under generated traffic.

The measurement is deliberately taken over eight requests on a clean sliding
window. A single source exceeding 30 requests per minute trips `RATE_ELEVATED`,
which contributes 0.4 to the rule score and, combined with a moderate ML score,
blocks subsequent traffic. An earlier version of the check issued 25 probes and
then measured a source the system had correctly flagged as bursty — which is a
different quantity from benign latency, and is noted because the same trap
applies to the Phase 9 harness.

## Model size: a constraint that was measured, not assumed

The 230 MB Random Forest is an obstacle to deploying this system anywhere except
the machine it was trained on: the small free container tiers allow 256-512 MB
of memory in total, so the artefact alone exhausts the budget before the Python
process starts. The obvious response is to bound the trees. It was tried,
measured, and rejected.

Constrained variants were fitted on the identical split, scaling and resampling,
then scored through the **full combined pipeline** at a threshold re-selected on
the validation split, because that is what the system actually deploys:

| Random Forest configuration | Threshold | Payload F1 | Payload FPR | All-rows F1 | Artefact |
|---|---:|---:|---:|---:|---:|
| **Unconstrained (retained)** | 0.77 | **0.9357** | **0.0596** | **0.8433** | 230 MB |
| `min_samples_leaf=5` | 0.79 | 0.8938 | 0.1060 | 0.7816 | 104 MB |
| `min_samples_leaf=10` | 0.76 | 0.8898 | 0.1225 | 0.8005 | 68 MB |
| `max_depth=24, leaf=5` | 0.76 | 0.8890 | 0.1243 | 0.8032 | 66 MB |
| `min_samples_leaf=20` | 0.74 | 0.8840 | 0.1328 | 0.8089 | 39 MB |
| `max_depth=20, leaf=10` | 0.75 | 0.8847 | 0.1306 | 0.8081 | 34 MB |
| `60 trees, depth 16, leaf=20` | 0.77 | 0.8788 | 0.1283 | 0.7771 | 9 MB |

Every constraint costs roughly five points of F1 on payload-bearing traffic and
**roughly doubles the false positive rate**, from 0.0596 to between 0.106 and
0.133. A high false positive rate is already this system's weakest result, so
paying more of it to save disk space is the wrong trade.

There is a methodological point here worth keeping. Judged on ROC AUC the
conclusion inverts: AUC *improves* as the forest shrinks, from 0.9591
unconstrained to 0.9687 for the smallest variant. An AUC-led selection would
have chosen the 9 MB model and quietly doubled the false positive rate. AUC
averages performance over every possible threshold, including regions this
system never operates in, whereas the deployed configuration uses exactly one
threshold, chosen on validation data. **A model selection metric that ignores
the operating point can rank a worse deployment above a better one.** The first
attempt at this change did exactly that, and it was caught only because the
combined-pipeline figures were re-checked after retraining.

The depth is therefore not waste. With 17 features and many near-duplicate
payload rows, the deep leaves separate benign from malicious patterns that
shallower trees blur together.

### Solving the size without touching the model

Persisting with `joblib.dump(..., compress=3)` instead of the default:

| | Artefact | Load time |
|---|---:|---:|
| Uncompressed | 229.8 MB | 3.5 s |
| `compress=3` | **45.6 MB** | **1.7 s** |
| `compress=6` | 42.2 MB | 1.5 s |

Smaller *and* faster to load, because reading 184 MB less from disk costs more
time than zlib spends expanding it. Level 3 is used; level 6 saves a further
3 MB for two and a half times the write cost. Predictions are bit-identical -
this changes distribution, not the model. The whole `ml/models/` directory is
now **45.9 MB**, and the inference container reaches its healthy state in about
16 seconds rather than the 40 seconds the Phase 7 health check allows for.

Resident memory is unchanged at roughly 260 MB. The deployment consequence is
that this system needs a host offering about 1 GB, not one of the 256 MB tiers -
a hosting decision rather than a modelling one.

## Hardening pass across Phases 0-7

Applied after Phase 7, before the attack simulation. Detection behaviour is
unchanged: all Phase 6 integration checks still pass in both normal and degraded
modes, and the feature parity test still reports 240 comparisons with no
divergence.

| Defect | Consequence | Fix |
|---|---|---|
| Sliding-window map entries were never removed once their event list emptied | One dead key per source address ever seen. Phase 8 generates traffic from many distinct sources, so this grows without bound | `sweep()` on an unref'd 60 s timer evicts empty entries; verified evicting 500 stale sources |
| No SIGTERM or SIGINT handler | `docker compose stop` killed the process outright, dropping in-flight requests and any `request_log` write in progress, then waited out the full 10 s grace before SIGKILL | Drain in-flight connections, close the Postgres pool, stop the timer. Verified in-container: exit code 0 after 1 s |
| `.env.example` documented 5 of 11 configuration variables | The six controlling detection behaviour - mode, strategy, weights, timeout, trace - were discoverable only by reading source | All documented, with defaults and the reasoning behind each |
| No test entry points in `package.json` | Tests were runnable only by knowing their paths | `npm test`, `test:parity`, `test:integration`, `test:integration:degraded` |
| The parity test hard-coded a Windows interpreter path | Could not gate a commit from Linux or inside the container | Resolves the interpreter across layouts, with a `PYTHON` override |
| The integration test produced false failures on a second run | The behavioural window keys on source address, which does not change between runs. A rerun without restarting begins about 28 events into the 60 s window, the rate rules fire, and the failures surface several checks later as apparent detection defects | `/health` reports window occupancy (counts only, never addresses); the test refuses to run against a dirty window and states how to clear it |
| The integration test asserted the 100 ms latency budget in degraded mode | Under Compose a stopped container swallows connections rather than refusing them, so the fail-open path waits out `ML_TIMEOUT_MS` in full. The test failed the system for correctly honouring NFR2 | The budget is now mode-aware: 100 ms with inference reachable, timeout plus margin without |

## Phase 8 - Attack Simulation and Threshold Recalibration

Four traffic generators (`attack-sim/`) send labelled attack and benign traffic
to the local API, each request recording the score the pipeline assigned it.
Each simulated client presents a distinct synthetic source address (RFC 5737
documentation range) so the behavioural features do not collapse the whole
harness into a single source; the API honours this only under `TRUST_PROXY=1`.
Per-request scores are captured from response trace headers under
`DETECTION_TRACE=1`, which is what makes the false positive rate not just
measurable but movable.

### What the benign traffic exposed

The generators reproduced the Phase 6 blocker with a precise diagnosis. Against
the hybrid pipeline the benign false positive rate was **17.5%**, and it was not
spread across the traffic - it concentrated on the authentication endpoints:

| Endpoint | Benign requests | Scoring >= 0.80 |
|---|---:|---:|
| `/api/auth/*` | 25 | 21 |
| `/api/orders/*` | 32 | 0 |
| `/api/search/*` | 64 | 1 |

The rule stage never false-fired (rule score 0.0 throughout, matching the 0% for
rules alone). The ML term was the cause: the payload classifier scored
credential POST bodies (`username=...&password=...`, high entropy, dense special
characters) at around 0.92, because that shape resembles the SQLi payloads it
was trained on far more than it resembles benign GET-search traffic.

A second symptom confirmed it. Brute force was blocked at the *first* attempt -
which cannot be real behavioural detection, since one failed login is
indistinguishable from a typo. The early block was the same ML mis-scoring of
the login body. The inflated attack recall and the benign false positives were
one bug seen twice.

### The fix, and why not the threshold

Threshold tuning could not resolve this. The curve shows benign FPR only reaching
an acceptable level at 0.85, where the ML term simultaneously stops catching the
SQLi the rules miss (recall 99% -> 83%): the benign auth scores sit on top of the
ML-only attack scores, leaving no clean cut.

The classifier's features - SQL keyword count, `UNION SELECT`, quote and comment
counts - describe a free-text query and are meaningless for a credential body.
The attacks that target auth (brute force, credential stuffing) are behavioural
and caught by the rate, failure-ratio and distinct-username rules, which need no
payload model. So the ML call was scoped to payload-bearing endpoints
(`config.mlPayloadPaths`, default `/api/search`); everywhere else the verdict is
the rule stage alone.

### Result

| Metric | Before | After |
|---|---:|---:|
| Benign false positive rate | 17.5% | **1.8%** |
| SQLi detection | 100% | 100% |
| Brute force | blocked at attempt 1 (ML artefact) | blocked at attempt 5 (failure-ratio rule) |
| Credential stuffing | blocked at username 1 (ML artefact) | blocked at username 5 (distinct-username rule) |

Attack recall at threshold 0.7 is **91.7%**, down from the earlier inflated 99%,
and that lower figure is the honest one: the first few brute-force attempts
genuinely cannot be distinguished from mistyped passwords, and counting them as
missed detections is correct. The two remaining benign false positives are
ambiguous searches - `usb-c hub` and `logitech's mx master` - where a dash or
apostrophe produces a real SQLi-like signal.

The recalibration (`evaluation/threshold_recalibration.md`) recommends 0.8 as a
further refinement (FPR 1.7%, recall 90.6%). It has not been applied: the scoping
fix alone cleared the blocker, and whether to also move the boundary is left for
the Phase 9 comparison to decide across all four configurations.

### Detection by attack type (threshold 0.7, after the fix)

| Attack type | Detected / total |
|---|---:|
| sqli (all six families) | 26/26 |
| brute_force | 26/30 |
| credential_stuffing | 38/46 |

The behavioural numbers are below 100% by design: attempts before the rule's
detection threshold is reached are, correctly, not blocked.

## Phase 9 — Comparative Evaluation

Not yet started.
