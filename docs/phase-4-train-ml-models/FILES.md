# Phase 4 — Files Created / Modified

| File | Purpose |
|---|---|
| `ml/train.py` | Training pipeline: stratified split, scaler, SMOTE, three models, 5-fold CV with resampling inside folds, per-source breakdown, feature importances, artefact persistence |
| `evaluation/results.md` | Phase 4 section added — test metrics, CV, per-source table, importances, zero-importance finding, inference cost |

## Generated artefacts (gitignored except `feature_order.json`)

| Artefact | Size | Notes |
|---|---:|---|
| `ml/models/random_forest.pkl` | 259 MB | Unconstrained depth; 16 ms median inference |
| `ml/models/xgboost.pkl` | 279 KB | 0.26 ms median inference, highest ROC AUC |
| `ml/models/isolation_forest.pkl` | 500 KB | Fitted on benign rows only |
| `ml/models/scaler.pkl` | 975 B | Fitted on the training split only |
| `ml/models/feature_order.json` | 471 B | **Tracked in git** — the contract Phase 5 and the middleware both bind to |
| `ml/models/training_summary.json` | 5 KB | Machine-readable metrics, CV, per-source and importances |

## Reproduce

```powershell
.\ml\venv\Scripts\python ml\train.py
```

Roughly four minutes on the full corpus, most of it cross-validation. Seeded at
42 throughout.

```powershell
.\ml\venv\Scripts\python ml\train.py --sample 60000 --no-cv
```

Fast path for verifying a pipeline change (about fifteen seconds).
