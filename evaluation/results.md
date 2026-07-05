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

Not yet started.

## Phase 9 — Comparative Evaluation

Not yet started.
