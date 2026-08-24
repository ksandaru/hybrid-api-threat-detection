# Phase 4 — Implementation Log

Status: **Complete.**

Full metrics are in `evaluation/results.md`. This file records how the training
pipeline was built and what the results mean.

---

### Step 1 — Fix the ordering before writing anything else

- **What:** Established the sequence as split, then scale, then resample —
  and wrote it into the module docstring before implementing it.
- **Why:** These three operations produce a plausible-looking model in any
  order. Only one order is correct, and the incorrect ones inflate reported
  performance by an amount that cannot be recovered after the fact. SMOTE
  before the split interpolates synthetic minority samples between rows that
  later land on opposite sides of it, so the model is evaluated partly on
  relatives of data it has already seen. Scaling before the split lets the
  test partition's distribution influence the transformation.
- **How:** Split on indices first, fit `StandardScaler` on the training split
  alone, then apply SMOTE to the scaled training split alone. The test split is
  transformed with the fitted scaler and otherwise never touched.

### Step 2 — Cross-validation with resampling inside the folds

- **What:** Used an imbalanced-learn `Pipeline` of scaler, SMOTE and classifier
  as the estimator passed to `cross_validate`.
- **Why:** Resampling the whole training set and then cross-validating leaks
  across folds, for the same reason resampling before the split leaks across the
  split. Synthetic samples generated from a row in fold 3 would appear in the
  training data of folds 1, 2, 4 and 5.
- **How:** The pipeline re-fits the scaler and re-runs SMOTE within each fold, on
  that fold's training portion only. Stratified 5-fold, seeded.

### Step 3 — Train the three models

- **What:** Random Forest (100 estimators), XGBoost (100 estimators, max depth 6),
  Isolation Forest (100 estimators, contamination set from the observed training
  attack ratio, fitted on benign rows only).
- **Why:** The two supervised models let bagging and boosting be compared on an
  identical representation. Isolation Forest answers a different question — what
  does normal look like, and what deviates from it — and therefore trains on
  benign data only.
- **How:** All seeded at 42 and parallelised across cores. Isolation Forest's
  anomaly scores are negated so that higher means more anomalous, matching the
  orientation of the supervised probabilities for ROC computation.

### Step 4 — Report per source, not only in aggregate

- **What:** Added a per-source breakdown of test-split performance.
- **Why:** The corpus is assembled from sources with structurally different
  feature coverage: flow rows carry no payload features, payload rows carry no
  flow features. A model can therefore satisfy an aggregate metric by learning
  which source a row came from rather than whether it is an attack. Aggregate
  numbers alone would not reveal that, and reporting only aggregates would have
  overstated what the models do.
- **How:** Carried the `source` column through the split and computed the full
  metric set per source. The result is reported in `evaluation/results.md` and is
  the most consequential finding of this phase.

### Step 5 — Smoke run before full run

- **What:** Ran the pipeline on a 60,000-row stratified subsample with
  cross-validation disabled before committing to the full corpus.
- **Why:** The specification's own guidance, and sound practice: a pipeline error
  surfaces in thirty seconds rather than after ten minutes of training.
- **How:** `python ml/train.py --sample 60000 --no-cv`. The flags were kept in the
  final script rather than removed, since the same fast path is useful whenever
  the pipeline changes.

### Step 6 — Measure inference cost

- **What:** Timed 200 single-request predictions per model after warm-up.
- **Why:** NFR1 sets a 100 ms budget, and a model that cannot be served inside it
  is not a candidate regardless of accuracy. Measuring now, rather than
  discovering it during Phase 9, keeps the option of retraining cheap.
- **How:** Loaded the saved artefacts, transformed a single row, and timed
  repeated calls. Results in `evaluation/results.md`.

---

## Findings

### The models cannot detect two of the three target attacks

Both classifiers assign exactly zero importance to `requests_per_min_ip`,
`login_failure_ratio`, `distinct_usernames_tried` and `unique_ip_count_window` —
the four flow features that are zero-filled throughout the offline corpus. A
constant column carries no information and the models correctly ignore it.

The consequence is that the trained classifiers have no basis on which to detect
brute force or credential stuffing. The features that would express those attacks
are precisely the ones they learned to disregard.

This was predicted in Phase 1 as a data limitation. It is now measured. It does
not weaken the hybrid argument, it strengthens it: the rule engine computes all
five flow features live and does not depend on their appearing in training data,
so for two of the three target attack categories the rule stage is not a cheap
pre-filter ahead of the classifier — it is the only stage with any signal at all.

### Aggregate metrics conceal a split down the middle of the corpus

Per source, the same XGBoost model recalls 99.7% of attacks on Kaggle SQLiV3 and
98.5% on CSIC 2010, but only 73.4% on CICIDS Tuesday and 39.7% on CICIDS
Thursday. Because the CICIDS rows are 86% of the corpus and 97% benign, they pull
the aggregate accuracy up while contributing most of the missed attacks.

Any single headline accuracy figure for this corpus is therefore misleading on its
own, and the Phase 9 evaluation should report per source or per attack type
rather than in aggregate alone.

### Random Forest costs sixty times more per prediction than XGBoost

Random Forest predicts in 16.01 ms at the median against XGBoost's 0.26 ms, while
scoring lower on ROC AUC (0.9602 against 0.9762). Its trees were grown without a
depth limit on a million resampled rows, producing a 259 MB artefact that takes
1.77 s to load.

The three models called in sequence cost roughly 21 ms at the median, which is
inside the budget but is dominated by one model that is not the best performer.
Constraining Random Forest's depth is the obvious lever if the end-to-end
measurement comes under pressure in Phase 9. It has not been applied yet, because
changing it now would invalidate the figures above for no present benefit.

### Cross-validation agrees with the held-out split

Cross-validated accuracy sits within 0.001 of the single-split result for both
models, with fold deviation of 0.0004 for Random Forest. The reported performance
is a property of the corpus rather than of one fortunate partition. No model
approaches perfect accuracy, which is the intended outcome — the methodology
states in advance that a near-perfect score would be treated as evidence of
leakage rather than success.
