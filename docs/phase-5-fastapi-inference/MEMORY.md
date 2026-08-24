# Phase 5 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **Three-way split introduced here, not in Phase 4.** The threshold had to be
  chosen somewhere, and choosing it on the test split would have made the
  reported test metrics optimistic. Retraining with a validation split cost one
  run and made the operating point defensible.
- **Threshold selected on payload-bearing rows only.** The flow-only sources are
  86% of the corpus, carry no request text and are 97.5% benign. A threshold
  fitted to the aggregate is dominated by traffic the deployed service will
  never see.
- **Weights and threshold live in the artefact, not in the service.** `ml/app.py`
  reads them from `feature_order.json` and only overrides from the environment.
  The service therefore cannot silently score a different combination from the
  one the operating point was measured against. Environment overrides remain so
  Phase 9 can sweep.
- **Isolation Forest normalised by training percentiles**, not min/max, so a
  single extreme row cannot compress the scale. Without any normalisation the
  third term of the weighted sum is meaningless, since the raw score has no
  fixed range.
- **Artefact load failures are reported through `/health`, not raised.** A
  service that exits on startup gives no diagnosis; one that answers
  "unavailable, here is the exception" can be fixed.
- **Unknown feature names are reported rather than dropped.** A mistyped name
  would otherwise be silently zero-filled and produce a plausible score, which
  is the worst possible failure mode for a detection component.

## The mistake worth remembering

The original deliverable check asserted that every hand-written SQL injection
string scored above every hand-written benign string. It failed, and the first
instinct was to conclude the model was broken.

It was not. The pipeline flags 3.5% of real benign payload rows. The three
hand-picked benign strings happened to land above the 90th percentile of the
benign score distribution for their feature neighbourhood. **Three strings are
not a distribution**, and an assertion built on them tests the strings rather
than the system.

Compounding it, one diagnostic printed `nb.iloc[0]` as a "sample" row from a
4,001-row neighbourhood. That row turned out to be the maximum-scoring row of
the set (0.768 against a median of 0.386), which briefly made the model look
inconsistent. Printing one row as though it characterises a distribution is a
trap; the summary statistics settled it in one step.

Both errors were in the test harness, not the system. The lesson generalises:
when a check fails, establish whether the check is sound before changing the
thing under test.

## Gotchas

- **Isolation Forest score orientation.** `score_samples` returns *higher for
  more normal*. Both `train.py` and `app.py` negate it so higher means more
  anomalous. Any future consumer must keep that orientation or the third term
  inverts.
- **The corpus is not shaped like live traffic.** 86% of it is network flow
  records with every payload feature zero. Any aggregate metric computed over it
  describes a population the deployed system does not see. Always report the
  payload-only figure alongside.

## Open items

- A benign login request shaped the way the middleware builds it scores 0.837
  and would be blocked. Borderline rather than systematic, but it suggests the
  corpus benign traffic does not fully cover this API's own traffic shape.
  Phase 8's benign generator gives the measurement that matters.
- Phase 6 must not let the ML score dilute the rule score on behavioural
  attacks, where it carries no signal (Phase 4 finding, confirmed at the service
  boundary here: behavioural vectors score 0.027).
