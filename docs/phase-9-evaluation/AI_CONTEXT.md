# Phase 9 — AI Context

## Original spec goal

> Rigorous comparative evaluation producing every figure/table the
> dissertation needs. (The marks live here.)

## Tasks (as written, `ml/evaluate.py` + driver script)

1. **Four configurations to compare:** (a) rule-only, (b) ML-only, (c)
   ModSecurity WAF (OWASP CRS container as external baseline), (d) hybrid
   (ours). Toggle configs via env/flags.
2. **Metrics per config:** accuracy, precision, recall, F1, false positive
   rate, latency p50/p95/p99 (added latency per request), CPU/memory of
   the detection path.
3. **Cross-dataset generalisation:** train on the combined corpus, evaluate
   on the held-out ATRDF 2023 set. Report the drop vs. internal test — this
   is a headline result.
4. **Figures** → `evaluation/figures/`: confusion matrices, ROC curves
   (with AUC), latency distribution/box plots, feature-importance bar
   charts, a bar chart comparing the 4 configs across metrics.
5. **Statistical test:** paired t-test across repeated runs comparing
   hybrid vs. each baseline; report p-values.
6. Write everything up in `evaluation/results.md`.

## Deliverable check (as written)

All four configs evaluated; cross-dataset numbers reported; all figures
generated; results.md complete with statistical tests.

## Suggested commit message (as written)

`feat: full comparative evaluation, cross-dataset test, figures`

## Status

**Not started.**
