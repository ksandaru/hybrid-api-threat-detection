# Phase 0 — Resume Notes for Claude Code

Status: **Complete.** Do not redo this phase; read this file only if
resuming work and needing to confirm what environment assumptions are safe
to make.

## Environment facts established in this phase (treat as ground truth)

- Runtime is **native Windows 11**, not WSL2. Do not suggest
  `wsl --install` or `/mnt/c` path handling — this project does not use
  WSL2.
- Node is **v22.21.1**, Python is **3.13.3** on this machine (not the
  spec's v20/3.11 — see `MEMORY.md` for why that's fine).
- Docker Desktop is installed and working (`docker compose version` v2.29.2).
- Git identity and `core.autocrlf true` are set **locally to this repo**
  only — do not assume they're set globally on the machine.
- A GitHub remote already exists:
  `https://github.com/ksandaru/hybrid-api-threat-detection.git`. Pushing is
  a visible/shared action — always confirm with the project owner before
  `git push`, even if a prior push was approved (approval is per-action, not
  standing).

## If you need to verify the environment again

```
node --version
python --version
docker --version
docker compose version
git config --get core.autocrlf
git config --get user.name
```

## What's NOT done yet

Everything past the empty scaffold — see the other phase folders in
`docs/` for what's in progress vs. not started. Phase 0 only covers
directory structure, gitignore, env template, and the root commit.
