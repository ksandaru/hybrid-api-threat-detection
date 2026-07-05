# Phase 4 — Resume Notes for Claude Code

Status: **Not started.** Hard dependency on Phase 1's
`datasets/processed/train.parquet` existing.

## Facts to reuse from earlier phases

- `ml/requirements.txt` already lists scikit-learn, xgboost,
  imbalanced-learn, joblib — no new dependencies should be needed.
- `feature_order.json` is intentionally **not** gitignored (see
  `.gitignore` — only `ml/models/*.pkl` is excluded) because Phase 5's
  FastAPI service and Phase 3's middleware both need this file as the
  shared contract.

## When this phase is done

Fill in `IMPLEMENTATION.md`, `MEMORY.md`, `FILES.md`, update status here.
