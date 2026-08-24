# Phase 8 — Memory (decisions, gotchas, lessons)

Status: **Complete.**

## Decisions made (and why)

- **The payload classifier is applied only to search endpoints, not to all of
  `/api/*`.** This is the most significant decision of the phase and it changed
  the architecture. The model's features describe a free-text query; a
  credential POST body is not one, and scoring it produced a 17.5% false
  positive rate on ordinary logins while adding nothing, because auth attacks
  are caught behaviourally. `config.mlPayloadPaths` gates the ML call.
- **`X-Forwarded-For` is trusted only under `TRUST_PROXY=1`, off by default.**
  Behavioural detection keys on source identity; trusting a client-supplied
  header lets an attacker rotate identity per request and defeat it. The harness
  needs distinct client identities, so the flag exists — but making it the
  default would ship the vulnerability.
- **Scores are exposed on every response under `DETECTION_TRACE=1`, not only on
  blocks.** Recalibration needs to know how close benign traffic came to the
  boundary, which means the score of allowed requests, which a 403-only body
  cannot provide.
- **Synthetic credential pairs, generated from a fixed seed.** Never a real
  leaked list. The attack is defined by the pattern of many usernames from one
  source; invented pairs reproduce it exactly, so real data would add ethics
  risk and no realism.
- **Labels recorded at send time.** The CSV says what a request was meant to be,
  independently of the verdict, so Phase 9 can score one against the other.
- **Traffic CSVs are gitignored; the recalibration report is committed.** The
  CSVs carry run timestamps and regenerate from fixed seeds. The analysis is a
  durable artefact like `results.md`.

## Gotchas

- **`req.path` is not the full path inside this middleware.** It is mounted at
  `/api`, so Express has already stripped that prefix: `req.path` is
  `/search/vulnerable`, not `/api/search/vulnerable`. The endpoint-scoping check
  matches against `req.originalUrl`, which keeps the whole path. The first
  version matched `req.path` against `/api/search` and silently disabled ML on
  every endpoint — searches included — which the trace headers caught before it
  reached a commit.
- **"Blocked at attempt 1" was not good detection.** For a behavioural attack it
  is a red flag: a brute force cannot be identified from a single failed login.
  The early block was the ML term mis-scoring the login body. After the fix,
  blocking begins at attempt 5 (brute force) and username 5 (credential
  stuffing), which is the behavioural rule firing at the threshold it is written
  for.
- **A single blended false positive rate hid the cause.** 17.5% across all
  endpoints looked like a threshold problem. Broken down by endpoint it was
  obviously an auth problem — 21 of 25 auth requests versus 1 of 64 searches.
  Always disaggregate a rate before tuning the thing it appears to point at.
- **Attack recall went *down* after the fix, from 99% to 91.7%, and that is
  correct.** The earlier number was inflated by the same bug that caused the
  false positives. The honest figure counts the first few undetectable
  brute-force attempts as misses.

## Lessons

- Representative benign traffic is not a formality to satisfy a deliverable; it
  is a measurement instrument. The 33% blocker from Phase 6 was invisible to the
  corpus-based evaluation and only appeared once traffic shaped like this API's
  own was generated. The generators earned their place by finding a real defect,
  not by confirming the system worked.
- A model applied outside its domain does not fail loudly. It returns confident,
  well-formed scores that are simply wrong, and only disaggregated measurement
  distinguishes that from correct operation.

## Open items for Phase 9

- Decide whether to also move the threshold to 0.8 (the recalibration
  recommendation) or keep 0.7. The scoping fix alone cleared the blocker; the
  threshold move is an independent refinement worth measuring across all four
  configurations rather than setting now.
- The generators give each client a distinct source, but a single-machine run is
  still not a load test. Phase 9 latency figures under generated traffic should
  say so.
