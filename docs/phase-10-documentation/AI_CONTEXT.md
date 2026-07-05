# Phase 10 — AI Context

## Original spec goal

> Make the artefact reproducible and close the loop for the dissertation.

## Tasks (as written)

1. Finalise `README.md`: architecture diagram, setup, run,
   reproduce-results instructions.
2. `docs/deployment-aws-feasibility.md`: a **written-only** section (no
   code, no account) describing how the stack would deploy to AWS if
   productionised — API + ML as containers on ECS Fargate behind an
   Application Load Balancer, RDS PostgreSQL, models in S3, logs in
   CloudWatch — and why local Docker was chosen for the controlled latency
   evaluation instead.
3. Tag a `v1.0` release.

## Deliverable check (as written)

A fresh clone + `docker compose up --build` reproduces the system; results
are regenerable; docs complete.

## Suggested commit message (as written)

`docs: finalise README, reproducibility, AWS feasibility write-up`

## Status

**Not started.** `docs/deployment-aws-feasibility.md` currently exists only
as a Phase 0 TODO stub; `README.md` has an initial draft from Phase 0 that
needs finalising once the full stack is real.
