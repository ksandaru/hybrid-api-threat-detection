# Phase 10 — Memory (decisions, gotchas, lessons)

Status: **Not started.**

## Known adaptation to carry into the final write-up

The dissertation's environment section should describe this project as
developed on **Windows 11 natively** (not WSL2/Ubuntu 22.04 as the original
build spec assumed), with the API and ML services running as **Linux
containers** (`node:22-slim`, `python:3.13-slim`) under Docker Compose for
the actual evaluation runtime. See
`docs/phase-0-environment-setup/MEMORY.md` for the full reasoning — this
should be stated plainly rather than glossed over, since it's a legitimate
and defensible methodological choice, not an error to hide.
