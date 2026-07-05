# Phase 5 — AI Context

## Original spec goal

> A Python service that loads the models and scores feature vectors.

## Tasks (as written, `ml/app.py`)

1. On startup, load the 4 `.pkl` files + `feature_order.json`.
2. `POST /predict`: accept `{ "features": { ... } }`, order features per
   `feature_order.json`, scale, get `predict_proba` from RF + XGB and an
   anomaly score from Isolation Forest, combine with weights (start
   `0.4*RF + 0.4*XGB + 0.2*IF_normalised`), return
   `{ score, is_attack, details, latency_ms }`.
3. `GET /health`.
4. Add a `Dockerfile` (python:3.13-slim — adapted from spec's 3.11-slim per
   Phase 0's version decision — install requirements, run `uvicorn`).

## Deliverable check (as written)

`curl` a benign feature vector → low score; a SQLi-like vector (high
keyword count, `OR 1=1`) → high score. `latency_ms` reported.

## Suggested commit message (as written)

`feat: FastAPI inference service serving hybrid model score`

## Status

**Not started.** Note: `ml/Dockerfile` already exists from Phase 0
scaffolding, using `python:3.13-slim` per the Phase 0 version decision.
