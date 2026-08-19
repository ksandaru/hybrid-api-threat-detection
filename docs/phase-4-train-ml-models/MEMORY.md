# Phase 4 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **Split, then scale, then resample — in that order, enforced by code layout.**
  Any other order inflates reported performance in a way that cannot be detected
  from the output. The ordering is stated in the module docstring so a future
  edit has to argue with it explicitly rather than reorder by accident.
- **SMOTE runs inside cross-validation folds**, via an imbalanced-learn pipeline,
  not once over the training set beforehand. Resampling first leaks synthetic
  relatives of each fold's validation rows into its training rows.
- **Isolation Forest is fitted on benign rows only.** That is what makes it an
  anomaly detector rather than a third supervised classifier. Its contamination
  parameter is set from the observed training attack ratio rather than guessed.
- **Per-source metrics are reported alongside aggregates.** Without them the
  corpus's structural split is invisible, and the aggregate figure would have
  been reported as if it described uniform performance. This turned out to be
  the most important reporting decision of the phase.
- **Random Forest depth was left unconstrained for now.** It is the slowest and
  largest model and not the most accurate, so constraining it is attractive — but
  changing it after measuring would invalidate every figure already recorded, for
  no benefit until Phase 9 shows whether the latency budget is actually under
  pressure. Recorded as a lever, not applied.
- **Kept `--sample` and `--no-cv` flags in the final script** rather than deleting
  them after the smoke run. Any future change to the pipeline wants the same fast
  path.

## The finding that matters most

Four features have **exactly zero** importance in both models:
`requests_per_min_ip`, `login_failure_ratio`, `distinct_usernames_tried`,
`unique_ip_count_window`.

These are zero-filled throughout the offline corpus, so this is arithmetically
inevitable rather than surprising — but seeing it measured changes how the
project's claims must be worded. **The trained models cannot detect brute force
or credential stuffing.** Any statement that the ML stage detects all three
target attack types would be false.

What the models actually contribute is SQL injection detection from payload
features, plus whatever `inter_arrival_time_variance` supports — and that single
feature is ranked first in both models, which is why the CICIDS rows are
classified at all.

Two consequences to carry forward:

- **Phase 6.** The weighted combination must not let an uninformative ML score
  dilute a confident rule score on behavioural attacks. A naive `0.5 × rule +
  0.5 × ml` would actively damage brute-force detection, because the ML term is
  near-random there. Consider weighting by attack family, or letting the rule
  score dominate when the flow features are non-zero.
- **Phase 9.** Report per source or per attack type. A single aggregate accuracy
  for this corpus is misleading, and the discussion needs the breakdown to make
  the hybrid argument honestly.

## Gotchas

- **The 259 MB Random Forest artefact.** Unconstrained depth on a million
  resampled rows. It loads in 1.77 s and predicts in 16 ms — sixty times slower
  than XGBoost, which also scores higher on ROC AUC. Not a bug, but a design
  consequence worth stating before Phase 5 loads all three models into a service
  that has to answer inside 100 ms.
- **Aggregate accuracy on this corpus is close to meaningless on its own.** 86%
  of rows come from one source that is 97% benign. A model that predicted
  "benign" for every CICIDS row would still post a high overall accuracy.

## Open items

- Random Forest depth constraint, if Phase 9 latency requires it.
- No `credential_stuffing` class exists in the corpus at all, so no model has
  ever seen a labelled example. Phase 8's synthetic traffic is the only source,
  and folding it back into retraining is a possible extension rather than
  something currently done.
