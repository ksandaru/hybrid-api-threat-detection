# Phase 1 — AI Context

Instruction context given to Claude Code for this phase, preserved from the
original build specification.

## Original spec goal

> A single, cleaned, labelled, feature-engineered training corpus + a
> held-out test set, saved to `datasets/processed/`.

> This is the highest-risk phase for a beginner. Do it carefully and
> document every decision — the dissertation needs dataset statistics.

## Datasets required (as written in the spec)

| Purpose | Dataset | Where | Notes |
|---|---|---|---|
| SQL injection | Kaggle SQLiV3 | kaggle.com/datasets/syedsaqlainhussain/sql-injection-dataset | ~31k labelled query strings, needs free Kaggle account |
| SQLi + web attacks (HTTP context) | CSIC 2010 | GitHub mirror (msudol/Web-Application-Attack-Datasets) | ~61k HTTP requests, normal + anomalous |
| Brute force + cred-stuffing proxy | CICIDS2017 | unb.ca/cic/datasets/ids-2017.html | Use Tuesday (FTP/SSH-Patator) + Thursday morning (Web brute force) only, to save space |
| Held-out REST API test set | ATRDF 2023 | github.com/ArielCyber/Cisco_Ariel_Uni_API_security_challenge | REST-specific. **NEVER train on this — test only.** |

## Tasks (as written)

1. Write download instructions in `datasets/README.md`. Do not commit raw
   data (gitignored).
2. Explore each dataset in `ml/notebooks/01_explore.ipynb`: shape, columns,
   label distribution, sample rows, class imbalance. Save a summary table to
   `evaluation/results.md`.
3. Preprocess (`ml/preprocess.py`): clean each dataset (strip column
   whitespace, drop `Infinity`/`NaN`, drop duplicates), build **two feature
   families** (payload-level from Kaggle SQLiV3 + CSIC 2010; flow-level from
   CICIDS), produce a unified labelled schema (features + binary label +
   `attack_type`), save `datasets/processed/train.parquet` and
   `datasets/processed/heldout_atrdf.parquet` separately.
4. Feature engineering (`ml/features.py`) — **shared contract**: the exact
   same feature vector logic must be mirrored in
   `api/middleware/featureExtractor.js`. Canonical feature list:
   - Payload-level: `payload_length`, `sql_keyword_count`,
     `single_quote_count`, `double_dash_count`, `semicolon_count`,
     `paren_count`, `equals_count`, `special_char_ratio`, `shannon_entropy`,
     `has_union_select`, `has_or_equals`, `has_comment`.
   - Flow-level (sliding window per IP, computed by the middleware at
     inference time): `requests_per_min_ip`, `login_failure_ratio`,
     `inter_arrival_time_variance`, `distinct_usernames_tried`,
     `unique_ip_count_window`.
5. Apply **SMOTE** on the training split only (never on test), via
   `imbalanced-learn`.

## Deliverable check (as written)

`datasets/processed/train.parquet` exists with engineered features +
labels; ATRDF held out separately; dataset stats written to
`evaluation/results.md`.

## Suggested commit message (as written)

`feat: dataset acquisition, cleaning, feature engineering, unified corpus`

## Beginner guidance (as written, carried into later phases too)

> Start each ML step on the smallest dataset (Kaggle SQLi) to get the
> pipeline green, then scale up.
