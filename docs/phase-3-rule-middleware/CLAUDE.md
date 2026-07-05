# Phase 3 — Resume Notes for Claude Code

Status: **Not started.** Hard dependency on Phase 1's `ml/features.py`
canonical feature contract existing first — `featureExtractor.js` must
mirror it exactly (same feature names, same order). Check
`docs/phase-1-datasets/CLAUDE.md` and `ml/features.py` before writing this
phase.

## Facts to reuse from earlier phases

- Per-IP sliding-window state is explicitly allowed to be in-memory
  (single-node dissertation scope) — document that limitation in this
  phase's `IMPLEMENTATION.md` rather than over-engineering a distributed
  store.

## When this phase is done

Fill in `IMPLEMENTATION.md`, `MEMORY.md`, `FILES.md`, update status here.
