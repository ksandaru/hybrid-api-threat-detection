# Phase 6 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **Noisy-OR instead of the specification's weighted mean.** A weighted mean
  would let a 0.027 ML score cancel a 0.90 rule verdict on brute force, making
  the hybrid worse than rules alone on two of the three target attacks. Noisy-OR
  is never below either input. All four strategies remain selectable via
  `COMBINE_STRATEGY` so Phase 9 can compare them as a result rather than take
  this on faith.
- **The ML score is rescaled before combining.** Its decision boundary is 0.77,
  not 0.5, so a raw 0.79 means "marginal", not "confident". Mapping it so the
  boundary lands at 0.5 was a correctness fix, not tuning.
- **The boundary is discovered from `/meta`, not hard-coded.** If the service is
  retrained with different weights, the middleware follows automatically.
- **High-severity rules short-circuit before the inference call.** Keeps the
  cascade cheap (1.2 ms for a rule-caught attack against 47.7 ms for the full
  path) and structurally prevents behavioural detection from being diluted.
- **Benign traffic is measured, not asserted per request.** The system has a
  known, real false positive rate. A test asserting otherwise would encode a
  false expectation and fail for a reason this phase cannot fix.

## Gotchas

- **Combining two scores on different scales is a silent bug.** Both are numbers
  in [0, 1] and neither is obviously wrong, so nothing fails loudly — the system
  simply blocks legitimate traffic. Whenever two scores are combined, check what
  value each treats as its decision boundary before assuming they are comparable.
- **A load-generating test measures the source it created.** The latency probe
  ran after the attack cases and issued enough requests to trip `RATE_ELEVATED`,
  so it measured a source the system had correctly flagged as bursty. Any harness
  that generates traffic changes the state the detector sees. This applies
  directly to the Phase 9 evaluation harness.
- **Express middleware can be `async`**, but every path must either call `next()`
  or send a response or the request hangs. The fail-open branch is what
  guarantees that here.

## The finding that blocks deployment

The hybrid blocked 2 of 6 benign requests where rules alone blocked none: 33%
false positive rate against 0%. Both were ML false positives.

The instructive one: a valid login with an 18-character username scored 0.783
and was blocked; a short username passes. `payload_length` is the classifier's
second most important feature and the corpus associates length with attacks, so
the model is using request length as a proxy for maliciousness rather than
reading the request.

This is the Phase 5 corpus finding surfacing at the system boundary. 86% of the
training corpus is network flow records resembling no HTTP request, and the
payload-bearing remainder is 40% attacks, so any request carrying text starts
from a high prior.

**Do not present the hybrid as deployable at this operating point.** Trading 33%
false positives for one extra detected attack class is a bad exchange for an
inline control. The honest framing for the dissertation is that the hybrid
demonstrably catches attacks rules miss, and that its precision is currently
limited by a corpus that does not represent the deployment traffic — which is a
data-availability finding, not a design failure.

## Open items for Phase 8 and 9

- Generate representative benign traffic, then re-select the ML threshold on it.
  The current 0.77 was chosen on corpus validation rows, which do not cover this
  API's traffic shape.
- Report rule-only and hybrid false positive rates side by side. Accuracy alone
  would hide the trade being made.
- Compare all four combination strategies rather than only the default.
- Beware the harness measuring its own generated load; keep sources under the
  rate thresholds or use distinct source identities.
