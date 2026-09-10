# AWS Deployment Feasibility

**Written-only.** No AWS account was created, no infrastructure was provisioned
and no cost was incurred. This document describes how the artefact would deploy
to AWS if productionised, what would have to change, and why local Docker was
the correct environment for the evaluation this dissertation actually performs.

Every figure quoted is measured from the running system, not estimated.

---

## 1. Why the evaluation ran locally

The choice was methodological, not a matter of convenience.

The central measurement in Chapter 5 is **added latency attributable to
detection**. The framework's non-functional requirement is under 100 ms, and
the measured figures are 3.98 ms at the median on the rule short-circuit path
and 54.94 ms (p95 90.28 ms) when the classifier is consulted. Those numbers are
meaningful only if detection is the sole variable.

On AWS, a request would traverse an Application Load Balancer, a VPC network
hop between two Fargate tasks, and a further hop to RDS. Each contributes its
own latency with its own variance, none of which is attributable to detection.
Worse, that variance is not constant: Fargate is multi-tenant and its
CPU-credit and network behaviour differ between task placements, so repeating
the experiment could produce different numbers for reasons entirely unrelated
to the framework. Isolating a ~50 ms detection cost from that noise would
require far more repetitions than the project's scope allowed, and the result
would still describe *AWS on that day* rather than the framework.

Running locally makes the comparison clean: the same host, the same process
model, the same traffic, with `DETECTION_MODE` as the only thing that changes
between configurations. That is what makes the paired comparison in §9.1
defensible.

A second reason is reproducibility. `docker compose up --build` reproduces the
entire stack from a fresh clone on any machine with Docker, at no cost and with
no account. A marker or examiner can regenerate every figure in this
dissertation. An AWS deployment would be reproducible only for someone holding
credentials and willing to pay for it.

The trade-off is honest and stated in the limitations: the results describe a
single-node deployment under single-client load. They are not a load test, and
they say nothing about behaviour under concurrency.

---

## 2. Target architecture

```
              Internet
                 │
                 ▼
        ┌──────────────────┐
        │  AWS WAF         │   OWASP managed rules — the signature tier
        │  (optional)      │   moves here; see §5
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │  Application     │   TLS termination, health checks,
        │  Load Balancer   │   round-robin across tasks
        └────────┬─────────┘
                 ▼
     ┌───────────────────────────────────────────────┐
     │  ECS Fargate — service: api                   │
     │  Node.js 22 container, 0.5 vCPU / 1 GB        │
     │  detection middleware, rule engine            │
     │  autoscaling 2–N tasks on ALB request count   │
     └──────┬────────────────────────┬───────────────┘
            │                        │
            │ scores                 │ writes
            ▼                        ▼
  ┌────────────────────┐   ┌────────────────────────┐
  │ ECS Fargate — ml   │   │ RDS PostgreSQL         │
  │ FastAPI container  │   │ Multi-AZ, request_log  │
  │ 1 vCPU / 2 GB      │   │ JSONB + GIN index      │
  │ models pulled from │   └────────────────────────┘
  │ S3 at startup      │
  └─────────┬──────────┘
            │ read at task start
            ▼
   ┌────────────────────┐        ┌────────────────────┐
   │ S3 — model store   │        │ ElastiCache Redis  │
   │ versioned prefixes │        │ shared sliding     │
   │ 43.7 MB artefacts  │        │ window — see §4    │
   └────────────────────┘        └────────────────────┘

   CloudWatch Logs + Metrics across all services
```

### Service sizing, from measured figures

| Service | Measured footprint | Proposed task size | Rationale |
|---|---|---|---|
| `api` | 38 MB resident | 0.5 vCPU / 1 GB | Node process is small; headroom is for concurrency, not the app |
| `ml` | **596 MB resident** | 1 vCPU / 2 GB | Random Forest is ~260 MB resident alone; 2 GB gives room for request handling without swapping |
| `db` | 29 MB (dev volume) | `db.t4g.micro`, Multi-AZ | Write-light: one row per inspected request |

The `ml` task size is the binding constraint and is the reason the smaller
Fargate configurations are unusable. This was established during the project
when the Random Forest was 230 MB uncompressed: `joblib` compression at level 3
reduced the artefact to 43.7 MB on disk and *improved* load time from 3.5 s to
1.7 s, but resident memory is unchanged, because compression affects storage
rather than the in-memory tree structure.

---

## 3. Model artefacts and S3

The models are 43.7 MB in total, dominated by the 43.5 MB Random Forest. They
are already bind-mounted rather than baked into the image, so the change to S3
is small: the container reads from a versioned S3 prefix at startup instead of
from a mounted volume.

```
s3://<bucket>/models/2026-08-19T22-37/
    random_forest.pkl        43.5 MB
    xgboost.pkl               0.1 MB
    isolation_forest.pkl      0.1 MB
    scaler.pkl                < 1 KB
    feature_order.json        < 1 KB      weights, threshold, iso calibration
```

Three properties of the current design carry over unchanged and are worth
noting because they were not designed with AWS in mind:

- **`feature_order.json` is the contract.** It carries the feature order, the
  ensemble weights and the selected threshold. The service reads its operating
  point from the artefact rather than from code, so promoting a new model is a
  prefix change and a task restart — no redeployment.
- **Startup already tolerates a missing model store.** `/health` reports
  `ready: false` with the reason rather than crashing, which is exactly the
  behaviour an ECS health check needs during a rolling deployment.
- **Load takes ~6 seconds.** The ECS health check grace period must exceed
  that, or tasks will be killed and replaced in a loop. The Compose health
  check already uses a 40-second start period for this reason.

Versioned prefixes plus S3 object versioning give rollback: point the task
definition at the previous prefix and restart.

---

## 4. The blocker: shared behavioural state

This is the one change that is not configuration, and it is the most important
paragraph in this document.

Five of the seventeen features are behavioural — request rate, login failure
ratio, inter-arrival variance, distinct usernames tried, unique sources per
endpoint. They are computed from a **60-second sliding window held in the API
process's memory** (`api/middleware/featureExtractor.js`).

That works for a single node. Behind an ALB with *N* tasks it fails, and it
fails silently:

- Requests from one attacker are distributed round-robin across tasks, so each
  task sees roughly 1/*N* of the attack.
- `CREDENTIAL_STUFFING` fires at 5 distinct usernames from one source. With
  four tasks, an attacker gets ~20 attempts before any single task accumulates
  5 — and if they distribute widely enough, none ever does.
- Nothing errors. The rules simply never fire, and detection of both
  behavioural attack types quietly degrades toward zero as the service scales
  out. **Scaling up makes the system less secure.**

The remedy is to move the window to a shared store — ElastiCache for Redis,
using a sorted set per source with timestamp scores and `ZREMRANGEBYSCORE` to
expire outside the window. The interface is small: `recordRequest` and
`computeFlowFeatures` are the only two functions that touch the store, and both
already take an explicit `now` parameter, so the change is contained.

The cost is a network round trip on the request path. At the measured 3.98 ms
median for the rule path, adding ~1 ms of ElastiCache latency is acceptable;
the same call on the ML path is negligible against 54.94 ms. But it must be
measured, not assumed, and it introduces a new dependency that the fail-open
policy would need to cover — an unreachable Redis must degrade to per-task
windows rather than failing the request.

**Until this is done, the framework is a single-node design.** That is stated
plainly in the dissertation limitations rather than presented as a deployment
detail.

---

## 5. Where the WAF tier belongs

The comparative evaluation found that ModSecurity with the OWASP Core Rule Set
achieves precision 1.0000 at a 0.0% false positive rate on this project's
benign traffic — better than this framework on both counts — while scoring 0%
on brute force and credential stuffing.

That result suggests a layered production design rather than a replacement:

| Tier | Handles | Rationale |
|---|---|---|
| AWS WAF / managed OWASP rules | Known injection signatures | Curated, cheap, zero measured false positives, runs at the edge before compute is billed |
| This framework's rule engine | Behavioural attacks | The WAF does not attempt rate or session analysis without extra configuration |
| This framework's classifier | Injection variants no rule describes | The measured contribution is on comment, stacked, blind and obfuscated families |

This is a more defensible architecture than the one evaluated, and the project
did not test it. It is named in the limitations as the most informative missing
comparison.

---

## 6. Observability and cost

**CloudWatch.** The trace output (`DETECTION_TRACE=1`) already emits one
structured line per decision with the rule score, ML score, combined score,
verdict and the rules that fired. As CloudWatch Logs with a metric filter, that
gives block rate, score distribution and rule-firing frequency without new
instrumentation. The score headers, useful diagnostically, would be **disabled
in production** — an attacker able to read their own score could binary-search
the threshold and stay beneath it.

**Alarms worth setting**, each derived from something the evaluation found:

- Block rate above a baseline — the false-positive incident found in simulation (17.5% of
  legitimate logins blocked) would have been caught within minutes by this.
- `ml` task `ready: false`, or a sustained rise in fail-open fallbacks — under
  Compose a stopped dependency costs the full 250 ms timeout per request, so an
  inference outage is visible as a latency step change before it is visible as a
  detection gap.
- p95 added latency above 100 ms, the stated NFR.

**Indicative monthly cost** at two `api` tasks, one `ml` task and a
`db.t4g.micro`, in `eu-west-1`, low traffic: roughly USD 90–120 for Fargate,
USD 25–30 for RDS Multi-AZ, under USD 1 for S3, and CloudWatch dominated by log
volume. The `ml` task is the largest single line item, which is a direct
consequence of the 596 MB resident footprint — and therefore of the decision,
documented in `evaluation/results.md`, to keep the Random Forest unconstrained
because every constrained variant roughly doubled the false positive rate.

---

## 7. Summary of what would have to change

| Change | Effort | Why |
|---|---|---|
| Read models from S3 rather than a mounted volume | Small | Already reads its operating point from the artefact |
| `DATABASE_URL` to RDS; secrets to Secrets Manager | Small | Credentials currently default to development values |
| Health-check grace period ≥ 6 s model load | Small | Otherwise tasks restart in a loop |
| Disable `DETECTION_TRACE` response headers | Small | Discloses the decision boundary |
| **Move the sliding window to ElastiCache** | **Substantial** | **Behavioural detection silently degrades when scaled out** |
| Re-measure latency under concurrency | Substantial | Present figures are single-client and not a load test |
| Retraining pipeline | Substantial | Models trained once on 2010–2017 corpora; no drift handling exists |

The first four are configuration. The last three are the honest boundary
between a working dissertation artefact and a production system, and the
dissertation claims only the former.
