# Phase 3 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **The keyword list in `ml/features.py` was not extended**, even though
  `TABLE` and `FROM` would have caught more payloads. That list defines the
  677,166-row corpus; changing it would silently invalidate every feature
  already computed and force a full rebuild. Detection gaps were closed by
  reweighting rules instead, which changes no feature value.
- **Rules read only the shared feature vector.** No rule inspects the raw
  request. This is what makes the rule score and the ML score combinable in
  Phase 6 — both stages judge the same representation — and it is stated as a
  design property in the dissertation's conceptual framework.
- **Rules are data, not branches.** A predicate plus a severity plus a weight,
  in a list. The active rule set can therefore be printed, tabulated in the
  dissertation, and swept by the Phase 9 evaluation without touching code.
- **Blocking is a threshold comparison, not just a severity check.** A
  high-severity rule rejects outright; otherwise accumulated medium signal must
  clear `DETECTION_THRESHOLD`. This makes the rule-only baseline a fair
  comparator, since it uses the same decision rule the hybrid will.
- **Feature extraction failure allows the request.** If extraction throws there
  is no basis on which to judge the request, and failing closed would turn a
  middleware bug into a full outage. Consistent with the fail-open policy in
  NFR2.
- **`DETECTION_MODE` added early** (`off` | `rules` | `hybrid`). Phase 9 needs
  to run four configurations; making that a configuration switch now avoids
  editing the request path later, when changes are riskier.

## Gotchas encountered

- **`req.url` is mutable during Express dispatch.** The mount path is stripped
  as a request descends into nested routers, so a path read inside a `finish`
  handler is not the path read on entry. Anything needed after an async
  boundary must be captured at entry. This cost the whole of Defect 1.
- **A blocked request has no application outcome.** Recording 403 as "not a
  401, therefore a successful login" was a semantic error that produced an
  oscillating block/allow loop. Requests that never reached the handler must be
  excluded from outcome statistics, not defaulted.
- **`sys.stdin.read()` on Windows uses the locale code page, not UTF-8.** The
  parity harness reported two failures that looked exactly like genuine
  contract divergence; the give-away was that the length differences matched
  the UTF-8 byte counts of the characters involved (3 for the coffee symbol,
  4 for the emoji). Read `sys.stdin.buffer` and decode explicitly.
- **`re.escape` escapes spaces in Python 3.7+**, so a two-word keyword becomes
  an escaped-space pattern. Harmless, since an escaped space matches a literal
  space in JavaScript too, but it is the kind of detail that has to be checked
  rather than assumed when porting regex-based features.

## Lesson carried forward

Every defect in this phase was behavioural and none was visible from the source.
The feature port looked correct, the rules looked correct, and the middleware
looked correctly mounted. What exposed the faults was running the sequence and
comparing the outcome against what the design predicted — the same discipline
that caught both preprocessing defects in Phase 1. Reading code confirms intent;
only execution confirms behaviour.

## Open items

- `login_failure_ratio` depends on the `finish` handler for request N running
  before request N+1 is evaluated. This holds for sequential clients and held
  throughout verification, but a highly concurrent attacker could interleave
  requests so that outcomes lag. Worth noting when interpreting Phase 9 results
  under load.
- Window state is per process and in memory. Documented in the dissertation as
  a scaling limitation.
