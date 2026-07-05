# Phase 4 — AI Context

## Original spec goal

> Three trained, saved models + a training report.

## Tasks (as written, `ml/train.py`)

1. Load `datasets/processed/train.parquet`. Split train/test (stratified,
   80/20). Apply SMOTE to the training split only. Fit a `StandardScaler`
   on train.
2. Train **Random Forest** (`n_estimators=100`), **XGBoost**
   (`n_estimators=100, max_depth=6`), **Isolation Forest** (`contamination`
   set from benign ratio; fit on benign only).
3. Print `classification_report` for each supervised model on the internal
   test split.
4. Save `random_forest.pkl`, `xgboost.pkl`, `isolation_forest.pkl`,
   `scaler.pkl` to `ml/models/`. Also save the canonical
   `feature_order.json`.
5. Write a training summary (per-model metrics, feature importances) to
   `evaluation/results.md`.

## Beginner guidance (as written)

> Start with ONLY the Kaggle SQLi data end-to-end to get the whole pipeline
> working, then add CSIC + CICIDS. Do not try to load all datasets at once
> on the first run.

## Deliverable check (as written)

Three `.pkl` files + `scaler.pkl` + `feature_order.json` exist. Supervised
models report sensible metrics (not 100% — that signals leakage;
investigate if so).

## Suggested commit message (as written)

`feat: train RF, XGBoost, Isolation Forest models with SMOTE`

## Status

**Not started.**
