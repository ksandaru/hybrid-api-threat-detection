# Phase 5 — Resume Notes for Claude Code

Status: **Complete.** Service runs, reproduces the offline measurement, and
reads its operating point from the trained artefact.

## Contract for Phase 6

`POST /predict` with `{"features": { ...17 names... }}` returns:

```json
{
  "score": 0.83,
  "is_attack": true,
  "threshold": 0.77,
  "details": { "random_forest": {...}, "xgboost": {...},
               "isolation_forest": {...},
               "missing_features": [], "unexpected_features": [] },
  "latency_ms": 41.2
}
```

Send all 17 names. Missing names are zero-filled and reported in
`details.missing_features`; unknown names are reported in
`unexpected_features`. If the middleware ever sees a non-empty
`unexpected_features`, the feature contract has drifted — treat that as a bug,
not as noise.

Any non-200, a timeout, or `"error"` in the body means fall back to the rule
verdict. Do not block because inference was unavailable.

## Weighting warning, carried from Phase 4 and confirmed here

Behavioural feature vectors score **0.027** at this service. The classifiers
assign zero importance to four of the five flow features because they are
zero-filled in the corpus. A naive `0.5 · rule + 0.5 · ml` would therefore
*halve* a confident rule score on brute force and credential stuffing and make
the hybrid perform worse than rules alone on two of the three target attacks.

Options, to be measured rather than argued:

- weight the rule term higher when the flow features are non-zero
- take `max(rule, ml)` rather than a weighted mean for the behavioural path
- keep the weighted mean but weight the ML term well below the rule term

Whatever is chosen, Phase 9 must show the hybrid does not underperform rules
alone on brute force. That is a live risk here, not a hypothetical.

## Facts to reuse

- Threshold 0.77, selected on the validation split over payload-bearing rows.
  Validation FPR 0.0541, test FPR 0.0596 — it transferred.
- Per-request service latency is roughly 40–60 ms end to end, dominated by
  Random Forest at ~16 ms. Budget is 100 ms including feature extraction and the
  HTTP hop, so headroom is real but not large.
- Report FPR on payload-bearing rows as well as in aggregate. The aggregate
  (0.87%) is flattered by the 86% of the corpus that is network flow records.
- Isolation Forest scores are negated so higher means more anomalous. Keep it.
