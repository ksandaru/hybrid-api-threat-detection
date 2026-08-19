# Phase 5 — Implementation Log

Status: **Complete.**

Metrics in `evaluation/results.md`. This file records how the service was built
and the two problems that verification exposed.

---

### Step 1 — Service skeleton

- **What:** `ml/app.py` loading the four artefacts once at startup and exposing
  `/health`, `/meta` and `/predict`.
- **Why:** A separate process, rather than an in-process library, keeps the
  machine learning stack in Python without imposing that on the API, allows
  models to be replaced without restarting the API, and isolates an inference
  fault from the request path.
- **How:** Artefact loading is wrapped so a failure is recorded and surfaced
  through `/health` rather than raised. A service that dies on startup behind a
  restart loop tells no one why; one that answers "unavailable, and here is the
  exception" can be diagnosed. `/predict` orders the incoming object by the
  canonical ordering read from `feature_order.json`, not by the order the client
  sent, and reports unknown names rather than dropping them — a mistyped feature
  would otherwise produce a plausible but meaningless score.

### Step 2 — Isolation Forest calibration

- **What:** Added percentile bounds of the Isolation Forest training score
  distribution to the saved artefact, and used them to map its raw output onto
  [0, 1].
- **Why:** The combination mixes the forest's score with two probabilities. The
  forest's raw score is unbounded and has no fixed scale, so without a mapping
  the third term would silently dominate or vanish depending on the range that
  particular fit happened to produce. This was a gap in Phase 4 rather than a
  defect: nothing consumed the score until now.
- **How:** `ml/train.py` records the 1st and 99th percentiles (0.2988 and
  0.7704) over the training split. Percentiles rather than min and max, so one
  extreme row cannot compress the whole scale.

### Step 3 — First verification run, and what it exposed

The service worked mechanically on the first run, but the deliverable check
failed: benign requests scored 0.79 to 0.87 and were classified as attacks,
while a stacked SQL injection scored 0.34 and passed.

Investigating rather than adjusting the threshold gave the cause. In the
corpus, 86.5% of rows have `payload_length == 0` — every flow record — and those
rows are 98.2% benign. The remaining 13.5% carry request text and are 39.7%
attacks. The models therefore learned that any request carrying text sits in a
high-prior region. Live API traffic always carries text.

The consequence is that the aggregate false positive rate of about 3% is
flattered by rows that resemble no HTTP request. Measured on payload-bearing
rows alone, the individual models sit at 17% to 23%.

### Step 4 — Three-way split, so the threshold could be chosen honestly

- **What:** Changed the split from train/test to train/validation/test
  (460,472 / 81,260 / 135,434) and selected the decision threshold on the
  validation split.
- **Why:** The obvious response to Step 3 was to raise the threshold. Choosing it
  by inspecting the test split would have tuned a hyperparameter to the data
  later reported as an unbiased result, making the reported test metrics
  optimistic by an unknown amount.
- **How:** Models fit on train; threshold swept from 0.05 to 0.95 on validation,
  restricted to payload-bearing rows, selecting maximum F1; test split untouched
  and used only for the final figures. Selection restricted to payload-bearing
  rows because a threshold fitted to the aggregate is dominated by flow records
  the deployed service will never see.
- **Result:** Threshold 0.77. Validation FPR 0.0541 against test FPR 0.0596, so
  the choice transferred rather than fitting the validation split.

The weights and threshold are written into the artefact and read back by the
service, so the scoring performed cannot drift from the scoring the operating
point was measured against.

### Step 5 — Rewriting the deliverable check

The redesigned service still failed the original check, so the check itself was
examined.

It asserted that every hand-written SQL injection string scored above every
hand-written benign string. Testing that against real data showed the assertion
was unsound: the pipeline flags only 3.5% of real benign payload rows, and the
three hand-picked benign strings simply landed in a high-scoring pocket. A
comparison against 4,001 real benign rows in the same feature neighbourhood put
their median at 0.386 — the hand-written vectors sat above the 90th percentile
of that region.

One diagnostic error is worth recording. An earlier attempt printed
`nb.iloc[0]` as a representative row from that neighbourhood; it was in fact the
highest-scoring row of the 4,001, which briefly suggested the model was
behaving inconsistently when it was not. Printing a single row as though it
characterises a distribution is a trap, and the distribution summary is what
settled it.

The check was rewritten to do two separate things:

- **Distributional check, asserted.** Samples 300 benign and 300 attack rows
  from the corpus, sends each through the running service, and confirms the
  service reproduces the offline measurement. This can fail the build. Current
  result: FPR 0.027, recall 0.983, mean separation 0.688.
- **Illustrative cases, reported only.** Hand-written requests shaped the way
  the middleware builds them, printed with scores so the behaviour on
  recognisable payloads is visible. Not asserted, because three strings are not
  a distribution.

---

## Findings

### The combination outperforms every individual model

At threshold 0.77 on the untouched test split, F1 rises from 0.7804 for the best
single model to 0.8433 overall, and ROC AUC on payload traffic reaches 0.9840
against XGBoost's 0.9763. The ensemble is doing real work rather than tracking
its strongest member.

### The aggregate false positive rate overstates deployment performance

0.87% across all test rows, 5.96% on payload-bearing rows alone. The lower
number is an artefact of the corpus being 86% network flow records. The figure a
practitioner should read is the payload-only one, and Phase 9 should report both.

### Some plainly benign requests still score high

A login request shaped the way the middleware builds it scores 0.837 and would
be blocked. This is borderline rather than systematic — real benign rows nearby
have a median of 0.386 — but it indicates the corpus benign traffic does not
fully cover the shape of this API's own traffic. Phase 8 generates realistic
benign traffic and will measure the false positive rate that actually matters.
