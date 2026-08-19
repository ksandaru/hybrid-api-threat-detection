# Phase 3 — Implementation Log

Status: **Complete.**

---

### Step 1 — Port the feature contract to JavaScript

- **What:** Wrote `api/middleware/featureExtractor.js`, implementing the same
  12 payload-level features as `ml/features.py`, in the same canonical order.
- **Why:** The specification's central warning is that a mismatch between the
  offline and online feature computation produces silently wrong predictions.
  The model keeps returning confident scores; they simply no longer mean what
  it learned they meant. Nothing about that failure is visible at runtime.
- **How:** Ported function by function against the Python source rather than
  from the feature names alone. Four places would have diverged under a naive
  translation:
  - Python's `len()` and iteration work over code points; JavaScript's
    `String.length` and index access work over UTF-16 code units. `Array.from()`
    is used throughout so multi-byte characters count identically.
  - Python's `str.count()` finds non-overlapping occurrences. `split().length - 1`
    reproduces that; a global regex would have too, but split is cheaper.
  - `re.escape` in Python 3.7+ escapes the space character, so `"group by"`
    becomes `group\ by`. That matches a literal space in JavaScript, so the
    two keyword patterns behave the same — verified rather than assumed.
  - Inter-arrival variance is emitted in **microseconds squared**, because
    `ml/preprocess.py` derives that feature by squaring CICIDS2017's
    `Flow IAT Std` column, which is recorded in microseconds. Emitting
    milliseconds would have placed live traffic on a scale roughly six orders
    of magnitude away from the data the models will be fitted on.

### Step 2 — Prove the contract holds

- **What:** Wrote `api/test/featureParity.js`, which runs both implementations
  over 20 payloads and compares all 12 payload features for each, failing on
  any divergence.
- **Why:** The claim that the two halves agree is the sort of thing that is
  easy to assert and hard to notice breaking. A test that executes both and
  compares is the only form of the claim worth making. It also gives the
  dissertation a concrete answer to NFR3 rather than an assurance.
- **How:** The Node process spawns the project interpreter, feeds the payload
  list to `ml/features.py` as JSON over stdin, and compares numerically with a
  tolerance of 1e-12 for the two floating-point features. Cases were chosen to
  exercise the divergence points above: empty input, overlapping separators
  (`a---b`), comment syntax, word-boundary keyword matching (`orange` must not
  match `or`), percent-encoded payloads, and multi-byte characters.
- **First run failed on two cases**, both multi-byte. The cause was in the test
  harness, not the feature code: `sys.stdin.read()` on Windows decodes using
  the locale code page, so the UTF-8 bytes for `☕` and `😀` were read as three
  and four separate characters respectively. Reading `sys.stdin.buffer` and
  decoding UTF-8 explicitly fixed it. Worth recording because the failure
  looked exactly like a genuine contract divergence and was diagnosed only by
  noticing that the reported lengths differed by precisely the UTF-8 byte
  counts.
- **Current result:** 20 payloads × 12 features = 240 comparisons, no divergence.

### Step 3 — Per-source sliding window

- **What:** Added an in-process store keyed by source address, holding recent
  request timestamps, paths, attempted usernames and authentication outcomes,
  plus a second store keyed by endpoint for the distinct-source count.
- **Why:** The flow-level features are the only signal available for brute
  force and credential stuffing; no single request in either attack is
  suspicious on its own.
- **How:** A 60-second window, pruned on each access rather than on a timer, so
  no background work is required and memory is bounded by traffic within the
  window. The window is updated *before* the features are read, so the current
  request is included in the statistics used to judge it — a burst is therefore
  visible on the request that completes it rather than only on the next one.
  Variance is population rather than sample variance, computed over at least
  three events so that a single gap does not produce a meaningless figure.

### Step 4 — Rule engine

- **What:** Wrote `api/middleware/ruleEngine.js` with 15 rules covering SQL
  injection payload shapes, request-rate anomalies, sustained authentication
  failure and username spraying. Returns `{ blocked, alerts, ruleScore }`.
- **Why:** This is both stage one of the cascade and baseline 1 of the Phase 9
  comparison, so it has to be genuinely representative of what a rule-based
  control achieves rather than a token implementation built to lose.
- **How:** Rules are expressed as data — a predicate, a severity and a weight —
  rather than as a chain of conditionals, so the active set can be printed,
  reported in the dissertation and swept during evaluation. Every rule reads
  only the shared feature vector, deliberately: the rule filter and the
  classifier judge the same representation, which is what makes their scores
  combinable in Phase 6. Thresholds are exported as a single object for the
  same reason.

### Step 5 — Orchestrator and wiring

- **What:** Wrote `api/middleware/detection.js` and mounted it at `/api` ahead
  of every route in `server.js`.
- **Why:** Mounting on the path prefix rather than on individual routes makes
  coverage structural — a newly added endpoint is inspected by default rather
  than by remembering to protect it.
- **How:** Extract, evaluate, decide, then log from a `finish` handler so the
  write is off the critical path. A high-severity rule rejects outright;
  otherwise accumulated medium signal must clear `DETECTION_THRESHOLD`. Feature
  extraction is wrapped so that a failure allows the request rather than taking
  the API down: if extraction fails there is no basis on which to judge the
  request, and failing closed would convert a middleware bug into an outage.
  Added `DETECTION_MODE` (`off` | `rules` | `hybrid`) so the Phase 9 baselines
  can be selected by configuration rather than by editing code.

### Step 6 — Verification against a running server

- **What:** Exercised benign traffic, four SQL injection variants, a brute
  force sequence and a credential stuffing sequence against a live server.
- **Why:** The specification's deliverable check for this phase is behavioural,
  and middleware ordering, body parsing and Express routing are exactly the
  things that reading the code confirms least reliably.
- **How:** Results below. Three defects were found this way; each is described
  in the next section.

| Case | Expected | Result |
|---|---|---|
| Benign searches (6, incl. `men's shirt`, `item #5`) | allow | 200 |
| Valid login | allow | 200 |
| `' OR '1'='1` | block | 403 |
| `' UNION SELECT username,password FROM users --` | block | 403 |
| `1; DROP TABLE users; SELECT 1` | block | 403 |
| `/**/or/**/1/**/=/**/1` | block | 403 |
| Brute force, 10 wrong passwords | block once established | 401 ×3, then 403 from attempt 4 |
| Credential stuffing, 8 distinct usernames | block once established | 401 ×4, then 403 from the 5th |

---

## Defects found during verification

### Defect 1 — Express rewrites `req.url` during dispatch

The `finish` handler recorded authentication outcomes by testing
`req.path.includes('/auth/login')`. Every brute force attempt returned 401 and
none was ever blocked, because the failure ratio stayed at zero.

Express strips the mount path from `req.url` as a request descends through
nested routers. The middleware is mounted at `/api`, so `req.path` reads
`/auth/login` on entry — but by the time the response finishes, the request has
also passed through the router mounted at `/api/auth`, and `req.path` reads
`/login`. The test never matched, so no outcome was ever recorded.

Fixed by using the path captured at entry, which is already stored on the
window event, instead of re-reading `req.path` later. The general point is that
`req.url` and anything derived from it are mutable during dispatch and must not
be treated as stable across an asynchronous boundary.

### Defect 2 — Blocked requests recorded as successful logins

After fixing Defect 1, brute force detection oscillated: attempts 4 and 6 were
blocked, attempts 5, 7 and 8 were not.

A blocked request returns 403. The handler recorded `loginFailed = (status === 401)`,
so a blocked attempt was recorded as a *successful* login. That pulled the
failure ratio below the threshold, which un-blocked the next attempt, which
then failed and pushed the ratio back up — a loop alternating between blocked
and allowed.

The error was semantic rather than mechanical. A blocked request never reached
the authentication handler, so its outcome is unknown, not successful. Blocked
requests are now left unresolved and excluded from the ratio entirely. Blocking
became sustained from the fourth attempt onward.

### Defect 3 — Inline-comment obfuscation evaded the tautology rules

`/**/or/**/1/**/=/**/1` was allowed. The comment markers split the tautology so
that the confirming conditions never held: no quote characters were present and
only one SQL keyword was matched, so the strong rule did not fire and the weak
one alone scored 0.4 against a threshold of 0.7.

This is the inline-comment evasion described by Qu et al. (2024), encountered
in the system rather than in the literature. Added a rule for the combination
of a tautology pattern with comment syntax, weighted so that it composes with
the weak tautology rule to 0.9 and clears the threshold, while neither alone
would. Kept at medium severity so the ML stage is still consulted in hybrid
mode rather than short-circuited.

---

## Tuning decisions worth stating

Two payloads initially scored below the threshold and were reweighted rather
than promoted to high severity:

- **Stacked query** (`1; DROP TABLE users; SELECT 1`) scored 0.4. `TABLE` is not
  in the keyword list, so only `DROP` and `SELECT` matched. The keyword list was
  deliberately **not** extended: it is the frozen contract the 677,166-row corpus
  was built against, and changing it would invalidate every feature already
  computed. The stacked-query rule was instead weighted to 0.7 so it clears the
  threshold unaided.
- **Quote with comment** (`admin'-- DROP TABLE`) is left at 0.5 and does not
  block on its own. The `has_comment` flag also covers `#`, which appears in
  ordinary text such as `item #5`, so promoting this to high severity would cost
  false positives. This remains a rule-only miss, and a useful one: it is exactly
  the kind of case the ML stage is expected to catch in Phase 6.

Both benign edge cases implied by those decisions were tested explicitly.
`men's shirt` and `item #5` both pass.
