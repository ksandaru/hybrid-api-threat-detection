# Phase 1 — Resume Notes for Claude Code

Status: **In progress.** Acquisition is done; preprocessing/features/parquet
are not.

## What to do next, concretely

1. Explore all four raw sources in `ml/notebooks/01_explore.ipynb` — shape,
   columns, label distribution, sample rows, class imbalance ratios. Watch
   for CICIDS's known leading-space column names and `Infinity`/`NaN`
   values.
2. Write `ml/features.py` first, as the canonical shared contract — define
   the feature list/order as a constant once, since
   `api/middleware/featureExtractor.js` (Phase 3) must mirror it exactly.
3. Write `ml/preprocess.py` to clean and unify all four sources into
   `datasets/processed/train.parquet` (Kaggle SQLiV3 + CSIC 2010 →
   payload-level features; CICIDS2017 → flow-level features), with
   `attack_type` labelled as `none`/`sqli`/`brute_force`/`credential_stuffing`.
   Keep ATRDF 2023 completely separate as `heldout_atrdf.parquet` — **never**
   merge it into the training split.
4. Apply SMOTE on the training split only, after the train/test split, not
   before.
5. Write dataset statistics into `evaluation/results.md`.
6. Per the spec's own beginner guidance: get the whole pipeline working on
   the Kaggle SQLi data alone first, then add CSIC 2010, then CICIDS2017.

## Facts to reuse from acquisition (don't re-derive)

- Raw file paths and exact filenames are listed in `FILES.md` — read that
  before writing `preprocess.py` so column-loading paths are correct on the
  first try.
- CICIDS2017 only has Tuesday + Thursday-morning (by design, per spec) —
  do not assume all 5 days are present.
- ATRDF `.7z` archives are not yet extracted (only `dataset_1_train.7z` was
  test-extracted). `preprocess.py` (or a prep step before it) will need to
  extract the others using 7-Zip
  (`"C:\Program Files\7-Zip\7z.exe" x <file>.7z`), since no `7z`/`7za` CLI
  is on PATH.
- ATRDF must never be used for training — only for the Phase 9 cross-dataset
  generalisation test.

## Commit message for this phase (once complete)

Adapt the spec's suggested
`feat: dataset acquisition, cleaning, feature engineering, unified corpus` —
confirm with the project owner before committing (per this project's
git safety convention: never assume commit approval carries over).
