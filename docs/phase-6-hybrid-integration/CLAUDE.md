# Phase 6 — Resume Notes for Claude Code

Status: **Complete.** The full pipeline runs end to end. One deployment blocker
is documented and belongs to Phase 8, not here.

## Read this before Phase 8 or 9

**The hybrid is not deployable at the current operating point.** It blocked 2 of
6 benign requests where rules alone blocked none — 33% false positive rate
against 0% — in exchange for catching one additional attack class. That is a bad
trade for an inline control.

The cause is the corpus, not the design. 86% of training rows are network flow
records resembling no HTTP request, and the payload-bearing remainder is 40%
attacks, so any request carrying text starts from a high prior. One false
positive is diagnostic: a valid login with an 18-character username scores 0.783
and blocks, while a short username passes, because `payload_length` is the
classifier's second most important feature.

**Phase 8 is the fix point.** Generate representative benign traffic, then
re-select the ML threshold on it. Do not present the hybrid as production-ready
until that is done.

## Do not "fix" these — they are correct

- **Behavioural attacks never reach the ML combination.** A high-severity rule
  short-circuits first. This is deliberate: the classifier scores brute force at
  0.027, so any averaging combination would cancel a correct rule verdict.
- **The ML score is rescaled before combining.** Its decision boundary is 0.77,
  not 0.5. Removing the rescale reintroduces the bug where a marginal ML verdict
  alone blocks legitimate traffic.
- **Benign traffic is measured as a rate, not asserted per request.** The false
  positive rate is real; an assertion would be a false expectation.

## Traps for the Phase 9 harness

- **A traffic generator measures the source it creates.** Exceeding 30 requests
  per minute from one source trips `RATE_ELEVATED` (0.4), which combines with a
  moderate ML score and blocks subsequent traffic. An earlier version of the
  integration check measured latency after issuing 40 requests and was measuring
  a source the system had correctly flagged as bursty. Use distinct source
  identities per simulated client, or stay under the thresholds.
- **Compare all four combination strategies**, not just the default. They are
  selectable via `COMBINE_STRATEGY` precisely so the comparison is a result.
- **Report rule-only and hybrid false positive rates side by side.** Accuracy
  alone hides the trade.

## Configuration reference

`DETECTION_MODE` (`off`/`rules`/`hybrid`), `DETECTION_THRESHOLD` (0.7),
`COMBINE_STRATEGY` (`noisy_or`/`weighted`/`max`/`rules_only`), `W_RULE`/`W_ML`,
`ML_TIMEOUT_MS` (250), `DETECTION_TRACE=1`.

Phase 9 builds its four configurations from `DETECTION_MODE` and
`COMBINE_STRATEGY` alone; no code changes are needed.

## Measured baseline for comparison

| | Hybrid | Rules only |
|---|---|---|
| p50 added latency | 47.7 ms | 6.1 ms |
| p95 added latency | 51.3 ms | 9.0 ms |
| Benign FPR | 33.3% | 0.0% |
| Attack rules miss | blocked (0.96) | allowed |
| Rule-catchable attacks | blocked | blocked |
| Rule-caught path latency | 1.2 ms (ML skipped) | 1.2 ms |
