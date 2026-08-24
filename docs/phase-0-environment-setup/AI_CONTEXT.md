# Phase 0 — AI Context

This is the instruction context given to Claude Code (the AI coding assistant)
for this phase. It is preserved verbatim/near-verbatim from the original
build specification so a supervisor can see exactly what the AI was asked to
do, and compare it against what was actually produced (see `IMPLEMENTATION.md`
and `FILES.md` in this folder).

## Original spec goal

> WSL2 Ubuntu ready with all tools; empty monorepo initialised inside WSL2
> and pushed to GitHub.

## Original spec tasks (as written)

1. Install WSL2 + Ubuntu 22.04 (Windows PowerShell, user-run).
2. Install Docker Desktop for Windows with WSL integration enabled.
3. Install VS Code + WSL extension.
4. Inside WSL2 Ubuntu: install Node.js 20, Python 3.11, verify Docker reaches
   through from Docker Desktop.
5. Create the monorepo directory structure (empty files with headers/TODOs
   are fine).
6. Add `.gitignore`, `.env.example`.
7. Configure git line endings for cross-platform safety
   (`core.autocrlf input`).
8. `git init`, first commit, create private GitHub repo, push.

## Deviation authorised by the project owner (this session)

The spec assumes development happens inside **WSL2 Ubuntu** to match the
dissertation's "Ubuntu 22.04" environment claim. Before starting, the AI
checked the actual machine state and found:

- WSL2 was installed, but **no `Ubuntu-22.04` distro existed** — only the
  internal `docker-desktop` distro Docker Desktop manages itself.
- The project owner was asked (via an explicit choice prompt) whether to
  install Ubuntu-22.04 first, or adapt the plan to native Windows.
- **Decision: adapt to native Windows.** Node and Python already installed
  natively (Node v22.21.1, Python 3.13.3) were kept rather than installing
  the spec's exact v20/3.11, again after an explicit confirmation prompt.

This is documented here, in `MEMORY.md`, and in the top-level
[README.md](../../README.md) so the reasoning is traceable for the
dissertation's methodology section.

## Deliverable check (as written in the spec)

`docker --version`, `node --version`, `python3.11 --version` (adapted:
`python --version`), and `docker compose version` all succeed. Project lives
under a fast local filesystem path. Repo pushed with the full empty
structure.

## Suggested commit message (as written in the spec)

`chore: scaffold monorepo structure and WSL2 tooling` (adapted in practice —
see `IMPLEMENTATION.md`).
