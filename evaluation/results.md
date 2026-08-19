# Evaluation Results

This file accumulates results across phases: dataset statistics (Phase 1),
per-model training metrics (Phase 4), the inference service and combined
scoring (Phase 5), and the full comparative evaluation (Phase 9). See `docs/phase-N-*/` for the what/why/how narrative behind each
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
| Random Forest | 16.01 ms | 26.04 ms | 27.28 ms | 259 MB | 1.77 s |
| XGBoost | 0.26 ms | 0.57 ms | 0.92 ms | 279 KB | 0.03 s |
| Isolation Forest | 5.11 ms | 6.60 ms | 7.27 ms | 500 KB | 0.03 s |

Random Forest costs roughly sixty times more per prediction than XGBoost while
scoring lower on ROC AUC, and its trees were grown without depth constraint on
the resampled training set, which is what produces the 259 MB artefact.
Constraining its depth is the obvious lever if the Phase 9 end-to-end
measurement comes under pressure; it has not been applied, because retraining
would invalidate the figures above for no present benefit.

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

## Phase 9 — Comparative Evaluation

Not yet started.
