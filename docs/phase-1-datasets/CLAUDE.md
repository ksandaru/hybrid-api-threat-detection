# Phase 1 — Resume Notes for Claude Code

Status: **Complete.** `ml/features.py`, `ml/preprocess.py`,
`datasets/processed/train.parquet` (677,166 rows), and
`datasets/processed/heldout_atrdf.parquet` (540,057 rows) all exist and are
correct (two silent-failure bugs were found and fixed — see `MEMORY.md`
and `IMPLEMENTATION.md` Bug 1/Bug 2 before modifying `preprocess.py`).

## Facts to reuse from this phase (don't re-derive)

- `ml/venv` already exists with all of `ml/requirements.txt` installed
  (relaxed to `>=` pins for Python 3.13 wheel compatibility — resolved to
  pyarrow 24.0.0, pandas 3.0.3, scikit-learn 1.9.0, xgboost 3.3.0). Use
  `./ml/venv/Scripts/python.exe` to run anything in `ml/`, don't recreate
  the venv.
- `CANONICAL_FEATURE_ORDER` in `ml/features.py` is the single source of
  truth for feature names/order — Phase 3's
  `api/middleware/featureExtractor.js` must mirror it exactly (same names,
  same order).
- CICIDS2017-derived rows genuinely have `login_failure_ratio`,
  `distinct_usernames_tried`, and `unique_ip_count_window` all zero
  (dataset format has no IP/username/timestamp columns) — this is correct,
  not a bug, and Phase 4's model training should be aware these three
  features carry zero training signal for the `brute_force` class from
  CICIDS specifically. They will only carry real signal from any live
  traffic captured through the Phase 3 middleware.
- ATRDF's `.7z` archives are extracted on-demand by `load_atrdf()` — first
  run after a fresh clone/checkout takes longer while it extracts all 8
  archives via 7-Zip (`C:\Program Files\7-Zip\7z.exe`, hardcoded path since
  no `7z` CLI is on PATH — if resuming on a different machine, check that
  path still resolves).
- **No credential_stuffing examples exist in `train.parquet`.** Don't be
  surprised when Phase 4's per-class metrics have nothing to report for
  that class — it's expected, see `MEMORY.md`.

## For Phase 4 (next consumer of this phase's output)

- Do the train/test split and SMOTE in `ml/train.py`, not here — Phase 1
  intentionally produces the full unsplit corpus.
- `inter_arrival_time_variance` for CICIDS rows is on a very large numeric
  scale (microseconds, squared) compared to the payload features (small
  integers/ratios) — make sure `StandardScaler` is fit before training, not
  skipped, or this one feature will dominate distance/gradient-based
  models.

## Commit message for this phase (already used)

`docs: detailed what/why/how log for Phase 0 and Phase 1` covered the
documentation; the actual `ml/features.py`/`ml/preprocess.py` code and
generated parquet files should be committed separately when the project
owner confirms (parquet files themselves are gitignored — only the code
is tracked).
