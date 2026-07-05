# Phase 0 — Memory (decisions, gotchas, lessons)

Things worth remembering when reading this phase later, or when a future
session/person resumes work on it.

## Decisions made (and why)

- **Native Windows instead of WSL2 Ubuntu.** The spec was written assuming
  WSL2, but no Ubuntu distro was installed and creating one requires an
  interactive step only a human can do. Rather than half-follow the spec,
  the whole environment strategy was confirmed with the project owner up
  front. This is the single biggest structural deviation from the original
  plan and affects wording in the dissertation's environment/methodology
  section — it should say "Windows 11 host, Linux-based Docker containers
  for the deployed services" rather than "developed on Ubuntu 22.04 in
  WSL2."
- **Node 22 / Python 3.13 instead of Node 20 / Python 3.11.** Kept the
  already-installed versions rather than installing older ones side by
  side, since both are current and fully compatible with every library the
  project needs (Express, FastAPI, scikit-learn, xgboost,
  imbalanced-learn). Avoids managing two Python/Node versions on one
  machine for no functional benefit.
- **Git identity set locally, not globally.** The machine had no git
  identity configured at all. Setting it `--global` would have silently
  changed authorship on every other repo on the machine, so it was scoped
  to this repo only after asking.

## Gotcha encountered: `.gitignore` swallowed placeholder files

- **What happened:** `datasets/raw/.gitkeep` and `datasets/processed/.gitkeep`
  were silently excluded from `git add -A` because the `.gitignore` rules
  `datasets/raw/` and `datasets/processed/` ignore the *entire directory*,
  including files meant to keep the (otherwise-empty) directory tracked by
  git.
- **Fix:** Changed the ignore rules to `datasets/raw/*` / `datasets/processed/*`
  plus explicit negations `!datasets/raw/.gitkeep` /
  `!datasets/processed/.gitkeep`. Directory-with-trailing-slash ignore
  patterns in `.gitignore` cannot be selectively un-ignored for files inside
  them — you have to ignore the *contents* (`dir/*`) instead of the
  directory itself for negation to work.
- **Why it matters going forward:** Any future addition of a gitignored
  directory that still needs to exist on fresh clone (e.g. a new
  `logs/` or `figures/` folder) must follow the same `dir/*` + `!dir/.gitkeep`
  pattern, not a bare `dir/` ignore.

## Process lesson: ask before destructive/irreversible git actions

- Early in the session a `git clone` was run into a project directory
  without asking first (an attempt to fetch the ATRDF dataset directly).
  The project owner rejected it and asked for confirmation to be sought
  before download/install actions going forward. This was corrected
  immediately and applied consistently afterward (see Phase 1's
  `MEMORY.md` for how downloads were subsequently confirmed one at a time).
