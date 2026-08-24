# Phase 4 — Resume Notes for Claude Code

Status: **Complete.** Three models, a scaler and `feature_order.json` are saved
under `ml/models/`. Metrics in `evaluation/results.md`.

## Read this before Phase 5 or 6

**The trained models cannot detect brute force or credential stuffing.** Both
classifiers assign exactly zero importance to the four flow features that are
zero-filled in the offline corpus (`requests_per_min_ip`, `login_failure_ratio`,
`distinct_usernames_tried`, `unique_ip_count_window`). Do not write anything
claiming the ML stage covers all three attack types — it covers SQL injection,
plus whatever `inter_arrival_time_variance` supports.

For those two attack categories the rule engine is the only stage with signal,
because it computes the flow features live from the sliding window rather than
reading them from training data.

## Consequence for Phase 6 weighting

A naive equal weighting would let a near-random ML score dilute a confident rule
score on behavioural attacks and make detection worse than rules alone. Options:

- weight the rule score higher when the flow features are non-zero
- keep the spec's `0.4 RF + 0.4 XGB + 0.2 IF` for the ML term, but weight the
  ML term itself lower against the rule term than an even split
- measure both in Phase 9 rather than choosing by argument

Whatever is chosen, the hybrid must be shown not to underperform rules alone on
brute force — that is a real risk here, not a hypothetical one.

## Consequence for Phase 5

Random Forest is 259 MB, loads in 1.77 s and predicts in 16 ms at the median —
sixty times slower than XGBoost, which also has the better ROC AUC (0.9762 vs
0.9602). All three models together cost about 21 ms median, 33 ms p95, before
HTTP and feature extraction. That fits the 100 ms budget but leaves less headroom
than it looks.

If Phase 9 latency comes under pressure, constraining Random Forest depth is the
first lever. It was deliberately not applied yet, because retraining now would
invalidate the recorded figures for no present gain.

## Facts to reuse

- `ml/models/feature_order.json` is the ordering the inference service must use
  when converting an incoming feature object into a vector. It is tracked in git
  precisely so Phase 5 can bind to it.
- The scaler must be applied before prediction, and it is the one fitted on the
  training split — do not re-fit.
- Isolation Forest scores are oriented so that **higher is more anomalous** in
  `train.py` (`-score_samples`). Keep that orientation in the service.
- Everything is seeded at 42; re-running reproduces the same figures.
