# Phase 0 — Implementation Log

Status: **Complete**

Each step below records **what** was done, **why** it was necessary, and
**how** it was carried out — written so it can be read directly by a
supervisor or lifted into the dissertation's methodology/setup section.

---

### Step 1 — Verify existing repo and environment state

- **What:** Checked whether `hybrid-api-threat-detection` was already an
  initialised git repo, and whether Docker/WSL2/Ubuntu were already present
  on the machine.
- **Why:** The build spec assumes a clean WSL2 Ubuntu environment. Before
  following the spec blindly, the actual machine state needed confirming so
  no step was skipped or wrongly duplicated.
- **How:** Ran `git status` in the target folder (found: empty repo, no
  commits). Ran `wsl --version` / `wsl -l -v` (found: WSL2 present, but only
  the internal `docker-desktop` distro — no `Ubuntu-22.04`). Ran
  `docker --version` and `docker compose version` from Git Bash on Windows
  (found: both working, Docker Desktop v27.2.0).

### Step 2 — Decide: WSL2 vs native Windows

- **What:** Asked the project owner whether to install WSL2 Ubuntu-22.04 (as
  the spec requires) or adapt the whole plan to run natively on Windows.
- **Why:** Installing Ubuntu-22.04 requires an **interactive** step (creating
  a Linux username/password) that only the human user can perform — the AI
  cannot do this unattended. It was also a meaningful fork in how every
  later phase would be executed, so it needed explicit sign-off rather than
  an assumption.
- **How:** Presented the trade-off directly (WSL2 matches the dissertation's
  "Ubuntu 22.04" claim exactly vs. native Windows is faster to start and
  still uses Linux-based Docker containers for the actual runtime). The
  project owner chose **native Windows**.

### Step 3 — Confirm actual Node/Python versions

- **What:** Checked installed Node and Python versions against the spec's
  required Node 20 / Python 3.11.
- **Why:** Found Node v22.21.1 and Python 3.13.3 already installed, with no
  Python 3.11 on PATH. Rather than silently using mismatched versions or
  silently installing older ones, this was flagged explicitly since it
  affects the dissertation's stated environment and could affect ML library
  compatibility.
- **How:** Ran `node --version`, `python --version`, `py -3.11 --version`
  (confirmed 3.11 not installed). Asked the project owner: install exact
  spec versions, or use what's already present. **Decision: use what's
  installed** (Node 22, Python 3.13) — both are current, fully compatible
  with Express/FastAPI/scikit-learn/xgboost/imbalanced-learn.

### Step 4 — Scaffold the monorepo directory structure

- **What:** Created the full directory tree from the spec's §2.1
  (`api/`, `ml/`, `datasets/`, `attack-sim/`, `evaluation/`, `docs/`), each
  file stubbed with a one-line `// TODO (Phase N): ...` comment describing
  what it will contain and which phase builds it out.
- **Why:** The spec explicitly asks for the empty structure to exist before
  any phase writes real code, so the whole team (or a supervisor) can see
  the intended shape of the project immediately, and later phases can be
  worked through incrementally without restructuring.
- **How:** Used `mkdir -p` to create all directories in one pass, then wrote
  each stub file individually with a short TODO comment referencing the
  phase that will implement it (e.g. `api/server.js` references Phase 2 and
  Phase 3).

### Step 5 — `.gitignore` and `.env.example`

- **What:** Added a `.gitignore` covering `node_modules/`, `ml/venv/`,
  `ml/models/*.pkl`, `datasets/raw/*`, `datasets/processed/*`, `.env`,
  Python caches, and log/figure output — with explicit `!...gitkeep`
  negations for `datasets/raw/`, `datasets/processed/` so those directories
  still exist on a fresh clone despite their contents being ignored. Added
  `.env.example` with `PORT`, `ML_SERVICE_URL`, `DATABASE_URL`,
  `DETECTION_THRESHOLD`, and `JWT_SECRET`.
- **Why:** Datasets and trained models are large, regenerable, and (for the
  raw datasets) redistributable only under their original licences — they
  must never be committed to git. `.env.example` documents required
  configuration without committing actual secrets.
- **How:** Wrote `.gitignore` directly; iterated once after discovering the
  first version accidentally ignored `.gitkeep` placeholder files inside the
  ignored dataset directories (see `MEMORY.md` for the bug and fix).

### Step 6 — Git identity and line-ending configuration

- **What:** Set `core.autocrlf true` **locally to this repo only** (not
  `--global`). Set `user.name` / `user.email` locally to this repo only.
- **Why:** The spec's `core.autocrlf input` setting is the WSL2/Linux
  convention; on native Windows the correct equivalent is `true` (checkout
  as CRLF, store as LF) to avoid noisy line-ending diffs. Git had no
  identity configured at all on this machine, which blocks every commit —
  this was surfaced to the project owner rather than assumed, since setting
  it `--global` would silently change authorship for every other repo on the
  machine.
- **How:** Asked the project owner directly for name/email and scope
  (local vs global). **Decision: local-only**, name "Kanishka Sandaruwan",
  email `ksandaru99@gmail.com`.

### Step 7 — Initial commit

- **What:** Staged all 36 scaffolded files and created the root commit.
- **Why:** Marks the end of Phase 0 per the spec's phase-by-phase commit
  discipline, and gives a clean baseline before any real logic is written.
- **How:** `git add -A`, then `git commit` with a message adapted from the
  spec's suggested `chore: scaffold monorepo structure and WSL2 tooling` to
  reflect the native-Windows adaptation:
  `chore: scaffold monorepo structure and tooling`.

### Step 8 — Push decision

- **What:** Confirmed a GitHub remote (`origin`) was already configured
  (`github.com/ksandaru/hybrid-api-threat-detection.git`), then explicitly
  asked before pushing.
- **Why:** Pushing is a visible, shared-state action (per working
  guidelines, anything visible to others requires explicit confirmation
  each time, not an assumed blanket approval).
- **How:** Asked the project owner; **decision at the time: hold off**
  (push deferred to a later point in the session).

---

## Deviations summary (see also `MEMORY.md`)

| Spec said | Actually used | Reason |
|---|---|---|
| WSL2 Ubuntu-22.04 | Native Windows 11 | No Ubuntu distro installed; interactive setup step; project owner chose native |
| Node 20 | Node 22.21.1 | Already installed, current LTS-equivalent, fully compatible |
| Python 3.11 | Python 3.13.3 | Already installed, no 3.11 present, fully compatible with the ML stack |
| `core.autocrlf input` | `core.autocrlf true` | Native Windows equivalent convention |
