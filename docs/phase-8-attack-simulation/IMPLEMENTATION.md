# Phase 8 — Implementation Log

Status: **Complete.** Four traffic generators produce labelled attack and benign
traffic against the local API, each request recording the score the pipeline
gave it. The benign traffic recalibrated the detection strategy and, in doing
so, exposed and fixed the Phase 6 false-positive blocker.

---

### Step 1 — A shared harness, not four scripts

- **What:** `attack-sim/common.py` — a `Client` that carries a synthetic source
  address, a `Recorder` that appends labelled rows to a CSV, and preflight
  checks. Every generator is a thin script on top of it.
- **Why:** The four generators share the same three ways of going wrong, and
  fixing each once is worth more than fixing it four times. The three:
  1. *Source identity.* Every behavioural feature — request rate, login failure
     ratio, distinct usernames tried — keys on the request's source. Twenty
     simulated clients from one machine are, without intervention, one source:
     they trip the rate rules collectively and the harness measures its own
     aggregate load. Each `Client` sends a distinct `X-Forwarded-For`, which the
     API honours only under `TRUST_PROXY=1`.
  2. *Labels at send time.* The CSV records what each request *was*, not what the
     system decided. Deriving the label from the response would make every
     configuration score 100%.
  3. *Dirty windows.* The 60-second window means a generator started right after
     another begins partway into a window it did not create; the rate rules then
     fire on traffic the current run did not send. `preflight()` refuses to run
     against a non-empty window.
- **How:** Synthetic client addresses come from the RFC 5737 documentation range
  (`203.0.113.0/24`), which is guaranteed non-routable, so a stray header can
  never name a real host.

### Step 2 — The API change the harness needs

- **What:** `TRUST_PROXY` (off by default) makes the API believe
  `X-Forwarded-For` when deciding a request's source.
- **Why:** Without it the harness cannot give clients distinct identities. It is
  off by default and warns loudly when on, because a detection system that
  trusts a spoofable source header lets an attacker rotate identity per request
  and never accumulate a window — every behavioural signal defeated by one
  header. This is acceptable only behind a proxy that overwrites the header, or
  in a controlled simulation.

### Step 3 — Recovering the score for every request

- **What:** Under `DETECTION_TRACE=1` the API now attaches `X-Detection-Score`,
  `X-Detection-Rule-Score` and `X-Detection-Ml-Score` to every inspected
  response, allowed ones included. The harness records them.
- **Why:** A blocked request returns its score in the body, but an allowed
  request discarded it — and the allowed benign requests are exactly the ones
  whose scores threshold recalibration needs. Without this, the false positive
  rate could be counted but not *moved*, because there was no record of how
  close each benign request came to the boundary.

### Step 4 — The four generators

- **`benign_traffic.py`** — registrations, logins, searches and order lookups
  across several clients, paced under 30 requests/minute so the rate rules do
  not fire on legitimate traffic. The searches deliberately include the awkward
  cases: apostrophes (`logitech's mx master`), quoted phrases, comparison
  operators, encoded input, non-ASCII, and words containing SQL keywords as
  substrings (`ordered`, `selection`, `android`). Leaving those out would
  calibrate the threshold against a strawman.
- **`sqli_attack.py`** — six SQLi families (tautology, union, comment, stacked,
  obfuscated, blind), labelled by sub-type so detection can be reported per
  family. The obfuscated family carries the payloads Phase 3 found evading the
  original rules.
- **`brute_force.py`** — one attacker, one victim username, many password
  guesses; never the real password. Records the attempt at which blocking began,
  which is the detection latency for this attack.
- **`credential_stuffing.py`** — many distinct synthetic usernames, one attempt
  each. Pairs are generated here from a fixed seed; they are **not** a real
  leaked list, which would be both an ethics violation and pointless, since the
  attack is characterised by the pattern of many usernames from one source and
  invented pairs reproduce it exactly.

### Step 5 — What the benign traffic revealed

Running the generators against the hybrid pipeline reproduced the Phase 6
blocker with a sharper diagnosis. Benign false positive rate: **17.5%**. But the
false positives were not spread across the traffic — they concentrated almost
entirely on the authentication endpoints:

| Endpoint | Benign requests | Scoring ≥ 0.80 |
|---|---:|---:|
| `/api/auth/*` | 25 | 21 |
| `/api/orders/*` | 32 | 0 |
| `/api/search/*` | 64 | 1 |

The rule stage never false-fired (`rule_score` 0.0 throughout, matching Phase
6's 0% for rules alone). The cause was the ML term: the payload classifier
scored credential POST bodies (`username=…&password=…`, high entropy, dense
special characters) at ~0.92, because that shape resembles the attack payloads
it was trained on more than it resembles the GET-search traffic it was
calibrated for.

A second, subtler symptom confirmed the diagnosis. Brute force was being
"blocked at attempt 1" — which looks like excellent detection but is the *same*
false positive: the very first login body scored high on ML. The inflated attack
recall and the benign false positives were two faces of one bug.

### Step 6 — The fix: apply the payload model only where it has signal

- **What:** `config.mlPayloadPaths` (default `/api/search`) restricts the ML
  call to payload-bearing endpoints. Everywhere else the verdict is the rule
  stage alone.
- **Why:** The classifier's features — SQL keyword count, `UNION SELECT`, quote
  and comment counts — describe a free-text query. They are meaningful for a
  search endpoint and meaningless for a credential body. The behavioural attacks
  that target auth (brute force, credential stuffing) are caught by the rate,
  failure-ratio and distinct-username rules, which need no payload model. So the
  model is applied where it has signal and withheld where it only has noise.
- **Why not just move the threshold:** The curve showed it could not work.
  Benign FPR only reached an acceptable level at 0.85, but at that point the ML
  term stopped catching the SQLi the rules miss (recall 99% → 83%): the benign
  login scores sat directly on top of the ML-only attack scores. There was no
  clean cut, because the problem was not where the boundary sat but what was
  being scored.

### Result

| Metric | Before | After |
|---|---:|---:|
| Benign false positive rate | 17.5% | **1.8%** |
| SQLi detection | 100% | 100% |
| Brute force | blocked at attempt 1 (ML artefact) | blocked at attempt 5 (failure-ratio rule) |
| Credential stuffing | blocked at username 1 (ML artefact) | blocked at username 5 (distinct-username rule) |

The two remaining benign false positives are genuinely ambiguous searches —
`usb-c hub` and `logitech's mx master` — where an apostrophe or dash produces a
real SQLi-like signal. Attack recall is now reported as 91.7% rather than the
earlier inflated 99%, which is the more honest figure: the first few brute-force
attempts genuinely cannot be distinguished from mistyped passwords, and counting
them as missed detections is correct.

The threshold recalibration (`evaluation/threshold_recalibration.md`) recommends
0.8 as a further refinement (FPR 1.7%, recall 90.6%). It has not been applied;
the scoping fix alone resolved the blocker, and moving the boundary as well is a
separate decision left for the Phase 9 comparison.

---

## Deliverable check

- Each generator runs and produces labelled requests the stack classifies. ✔
- Benign traffic mostly passes (1.8% blocked); attack traffic mostly blocked
  (SQLi 100%, behavioural attacks blocked once their rule threshold is reached). ✔
- Results logged to `evaluation/traffic/*.csv`, one row per request with its
  label, score and outcome. ✔
- Feature parity (240 comparisons) and Phase 6 integration (8 checks, normal and
  degraded) still pass after the detection change. ✔
- Ethics: all traffic targets only this project's local API; credential-stuffing
  pairs are synthetic. ✔
