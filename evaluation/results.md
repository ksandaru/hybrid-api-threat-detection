# Evaluation Results

This file accumulates results across phases: dataset statistics (Phase 1),
per-model training metrics (Phase 4), and the full comparative evaluation
(Phase 9). See `docs/phase-N-*/` for the what/why/how narrative behind each
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
Reproduce with `.\ml\venv\Scripts\python ml\train.py`; all randomness is seeded
at 42.

### Procedure

Stratified 80/20 split (541,732 train / 135,434 test), `StandardScaler` fitted
on the training split only, then SMOTE applied to the training split only,
raising it to 1,008,186 balanced rows. Cross-validation runs SMOTE **inside**
each fold through an imbalanced-learn pipeline, so no synthetic sample derived
from a validation row can appear in that fold's training data.

### Held-out test split (135,434 rows)

| Model | Accuracy | Precision | Recall | F1 | FPR | ROC AUC |
|---|---:|---:|---:|---:|---:|---:|
| Random Forest | 0.9666 | 0.7028 | 0.9005 | 0.7895 | 0.0284 | 0.9602 |
| XGBoost | 0.9562 | 0.6263 | 0.9180 | 0.7446 | 0.0409 | 0.9762 |
| Isolation Forest | 0.9159 | 0.4361 | 0.7181 | 0.5427 | 0.0693 | 0.8965 |

Isolation Forest is unsupervised and was fitted on benign training rows only.
Its weaker precision is expected and is the accepted cost of detecting attack
shapes absent from the training labels.

### Stratified 5-fold cross-validation (training split)

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
|---|---:|---:|---:|---:|---:|
| Random Forest | 0.9661 ± 0.0004 | 0.6992 ± 0.0033 | 0.8982 ± 0.0032 | 0.7863 ± 0.0022 | 0.9617 ± 0.0010 |
| XGBoost | 0.9579 ± 0.0017 | 0.6362 ± 0.0117 | 0.9202 ± 0.0030 | 0.7522 ± 0.0072 | 0.9765 ± 0.0009 |

Cross-validated figures sit within 0.001 of the single held-out split for both
models, and fold-to-fold deviation is small. The test-split result is therefore
a property of the corpus rather than an artefact of one partition. No model
approaches perfect accuracy, which is the outcome sought: as stated in the
methodology, a near-perfect score here would have been treated as evidence of
leakage requiring investigation rather than as success.

### Per-source performance (XGBoost, test split)

| Source | Rows | Attacks | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Kaggle SQLiV3 | 6,079 | 2,204 | 0.8931 | 0.7736 | 0.9968 | 0.8711 | 0.1659 |
| CSIC 2010 | 12,281 | 5,023 | 0.8634 | 0.7555 | 0.9849 | 0.8551 | 0.2206 |
| CICIDS2017 (Tuesday) | 84,344 | 1,863 | 0.9684 | 0.3868 | 0.7338 | 0.5066 | 0.0263 |
| CICIDS2017 (Thursday) | 32,730 | 320 | 0.9714 | 0.1458 | 0.3969 | 0.2133 | 0.0230 |

The aggregate figures conceal a split down the middle of the corpus. On the two
payload-level sources the classifier recalls 98–99% of attacks; on the two
flow-level sources it recalls 73% and 40%. The aggregate is dominated by the
CICIDS rows, which are 86% of the corpus and 97% benign, so a model can post a
high overall accuracy while performing poorly on precisely the attack classes
those rows were included to represent.

### Feature importances

| Rank | Random Forest | | XGBoost | |
|---|---|---:|---|---:|
| 1 | inter_arrival_time_variance | 0.2849 | inter_arrival_time_variance | 0.3206 |
| 2 | payload_length | 0.2718 | payload_length | 0.3169 |
| 3 | shannon_entropy | 0.1779 | shannon_entropy | 0.0818 |
| 4 | special_char_ratio | 0.1318 | has_comment | 0.0781 |
| 5 | equals_count | 0.0808 | sql_keyword_count | 0.0661 |
| 6 | sql_keyword_count | 0.0185 | special_char_ratio | 0.0424 |

### Four features carry zero importance in both models

Both classifiers assign **exactly zero** importance to the same four features:

- `requests_per_min_ip`
- `login_failure_ratio`
- `distinct_usernames_tried`
- `unique_ip_count_window`

These are the four flow features that are zero-filled throughout the offline
corpus, for the reasons recorded in the Phase 1 statistics above: the CICIDS2017
distribution format carries neither source addresses nor timestamps, so they
cannot be derived from it, and the payload-level sources are single requests with
no window to compute them over. A constant column carries no information, and the
models correctly ignore it.

The consequence is material and is carried into the discussion. **The trained
classifiers cannot detect brute force or credential stuffing**, because the only
features that would express those attacks are the ones they learned to disregard.
The single flow feature that does carry signal, `inter_arrival_time_variance`, is
the highest-ranked feature in both models — which is why the CICIDS rows are
classified at all, and why recall there is 73% rather than near zero.

Detection of the two behavioural attack categories therefore rests entirely on
the rule engine, which computes all five flow features live from the sliding
window and does not depend on their appearing in the training corpus. This is
not a defect in the models; it is a direct consequence of a documented gap in the
publicly available data, and it sharpens rather than weakens the argument for a
hybrid design: the rule stage is not a cheap pre-filter for the classifier, it is
the only stage with any signal at all for two of the three target attacks.

### Inference cost (single request, 200 timed calls after warm-up)

| Model | p50 | p95 | p99 | Artefact size | Load time |
|---|---:|---:|---:|---:|---:|
| Random Forest | 16.01 ms | 26.04 ms | 27.28 ms | 259 MB | 1.77 s |
| XGBoost | 0.26 ms | 0.57 ms | 0.92 ms | 279 KB | 0.03 s |
| Isolation Forest | 5.11 ms | 6.60 ms | 7.27 ms | 500 KB | 0.03 s |

Random Forest costs roughly sixty times more per prediction than XGBoost while
scoring lower on ROC AUC, and its trees were grown without depth constraint on
a million resampled rows, which is what produces the 259 MB artefact. Calling
all three models sequentially costs approximately 21 ms at the median and 33 ms
at the 95th percentile, before feature extraction, serialisation or the HTTP
round trip are counted. That remains inside the 100 ms budget set by NFR1, but
Random Forest accounts for most of it. Constraining its depth is the obvious
lever if the end-to-end measurement in Phase 9 comes under pressure, and the
trade-off it represents is revisited in the discussion.

## Phase 9 — Comparative Evaluation

Not yet started.
