# Phase 1 — Implementation Log

Status: **Complete** — all four raw datasets acquired; feature engineering,
preprocessing, and the unified parquet corpus are built. (Interactive
notebook exploration in `ml/notebooks/01_explore.ipynb` was not filled in —
the same exploration was done directly against the data while writing
`preprocess.py`, and its findings are captured here and in
`evaluation/results.md` instead.)

---

## Part A — Dataset acquisition

### Step 1 — Establish what can be downloaded automatically vs. needs a human

- **What:** Before downloading anything, checked which sources need
  authenticated access (Kaggle account, UNB registration form) vs. which are
  fully public (GitHub repos).
- **Why:** Entering credentials or submitting forms with personal
  information on the project owner's behalf is out of scope for the AI to
  do unattended — those steps needed the human to actually perform the
  login/registration, with the AI only automating the mechanical parts
  (clicking "Download", moving files, extracting archives) once
  authenticated.
- **How:** Attempted `list_connected_browsers` (browser automation tool) —
  initially empty (no Chrome extension connected). Asked the project owner
  to install/connect the Claude for Chrome extension. Re-checked after
  confirmation and got a connected browser session.

### Step 2 — Kaggle SQLiV3 dataset

- **What:** Downloaded `SQLiV3.csv`, `sqli.csv`, `sqliv2.csv` (~31k labelled
  SQL query strings/payloads) from
  `kaggle.com/datasets/syedsaqlainhussain/sql-injection-dataset`.
- **Why:** This is the spec's designated payload-level SQLi source and the
  smallest dataset — per the spec's own "beginner guidance," it's the
  dataset to get the whole pipeline working end-to-end on first.
- **How:** Navigated the connected browser to the Kaggle dataset page.
  Found the page required sign-in (not logged in — showed "Sign In" /
  "Register"). The project owner logged in manually in that browser tab
  (credential entry is never done by the AI). Confirmed login via
  screenshot (account avatar replaced the Sign In button). Clicked
  "Download" → opened a menu with options (kagglehub code snippet vs.
  "Download dataset as zip (1 MB)"). **Asked for explicit confirmation**
  (filename, source, size) before triggering the actual download, per
  working policy that file downloads always require a confirm step, then
  clicked "Download dataset as zip". File landed in the Windows Downloads
  folder as `archive.zip` (1.14 MB actual size). Copied it into
  `datasets/raw/kaggle_sqliv3/archive.zip` and extracted with `unzip`.

### Step 3 — CSIC 2010 dataset

- **What:** Downloaded the combined CSIC 2010 + ECML/PKDD 2007 CSV
  (`csic_ecml_final.csv`, HTTP requests labelled normal/anomalous) plus the
  original raw HTTP request text files and README.
- **Why:** This is the spec's designated HTTP-context SQLi/web-attack
  source, complementing the Kaggle payload-only strings with full request
  context (headers, method, body).
- **How:** Direct browser navigation to `github.com/...` was blocked by the
  browser automation tool's domain allowlist, so switched to command-line
  `git clone`. A first `git clone --depth 1` attempt of the full
  `msudol/Web-Application-Attack-Datasets` repo **timed out after 2
  minutes** (repo is 579 MB including `WekaData/` and PCAP-derived data not
  needed here). Rather than retrying blindly, the project owner **manually
  cloned the repo themselves** into
  `repository/Web-Application-Attack-Datasets` (outside the project, since
  it's a large one-time source, not project-tracked content). The AI then
  copied only the needed pieces into the project: `CSVData/csic_final.csv`,
  `CSVData/csic_ecml_final.csv`, and the original raw
  `OriginalDataSets/csic_2010/` request files (train/test .txt files +
  README), skipping `WekaData/` and `ecml_pkdd/` as out of scope.

### Step 4 — CICIDS2017 dataset

- **What:** Needed `Tuesday-WorkingHours.pcap_ISCX.csv` (FTP-Patator /
  SSH-Patator brute force) and
  `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` (Web brute
  force, XSS, SQLi) per the spec's guidance to use only these two days.
- **Why:** These specific days contain the brute-force and web-attack
  labels the project needs; downloading all 5 days (the full ~800 MB
  dataset) would be wasteful per the spec's own space-saving note.
- **How:** The official source (`unb.ca/cic/datasets/ids-2017.html`) links
  to `cicresearch.ca/CICDataset/CIC-IDS-2017/`, which turned out to require
  filling in a registration form (name, email, organisation, country)
  before unlocking the file browser — confirmed by testing direct file URLs
  on the underlying server (`205.174.165.80` / `cicresearch.ca`), which all
  redirected back to a generic page without a valid session. That domain
  was also blocked in the browser automation tool. Submitting a form with
  personal details is something the AI does not do on the user's behalf, so
  the **project owner filled in and submitted the form themselves** in
  their own regular browser, then started a download from
  `browse.php?p=CIC-IDS-2017%2FCSVs` — which showed no file size and was
  running with an unclear ETA.
  While that download ran, the AI checked three alternative sources the
  project owner had also found:
  1. `kaggle.com/datasets/chethuhn/network-intrusion-dataset` — confirmed
     working: a CC0-licensed mirror of all 8 official CICIDS2017 daily
     CSVs, byte-for-byte the same official dataset structure, with
     per-file download available (not just a bulk zip).
  2. `unb.ca/cic/datasets/ids-2017.html` — confirmed working as the
     description page, but it does not host files itself.
  3. `github.com/rokibulroni/CIC-IDS-2017-Dataset` — confirmed **not**
     useful: it only documents links to the same UNB server, hosts no
     actual data.
  The project owner cancelled the slow/unknown-size UNB download and asked
  to proceed with the Kaggle mirror instead. The AI selected the two
  specific files needed (via Kaggle's per-file "select=" UI), asked for
  explicit confirmation of filename/size for each
  (`Tuesday-WorkingHours.pcap_ISCX.csv`, 135.08 MB;
  `Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv`, 52.02 MB), and
  downloaded both. Files landed in Windows Downloads as `.zip`; copied into
  `datasets/raw/cicids2017/`, extracted, and the redundant zip copies
  deleted to save space.

### Step 5 — ATRDF 2023 held-out dataset

- **What:** Downloaded the API Traffic Research Dataset Framework (4
  datasets of increasing complexity, each split train/val, `.7z`
  compressed) from
  `github.com/ArielCyber/Cisco_Ariel_Uni_API_security_challenge`.
- **Why:** This is the spec's designated **held-out, never-train-on**
  cross-dataset generalisation test set — the headline result for the
  dissertation's evaluation phase depends on this being kept fully separate
  from training data.
- **How:** An initial unattended `git clone` attempt by the AI (before this
  policy was corrected — see `MEMORY.md`) was rejected by the project
  owner. The project owner then **manually cloned the repo themselves**
  into `repository/Cisco_Ariel_Uni_API_security_challenge`. The AI copied
  the `Datasets/` folder (8 `.7z` archives) and `README.md` into
  `datasets/raw/atrdf_2023/`, then test-extracted `dataset_1_train.7z`
  using the locally installed 7-Zip (`C:\Program Files\7-Zip\7z.exe`, since
  no `7z`/`7za` CLI was on PATH) to confirm the archive format was readable
  — it extracted cleanly to a JSON file.
- **Note:** A stray empty `.git/` directory was found inside
  `datasets/raw/atrdf_2023/` — a leftover from the AI's earlier rejected
  clone attempt at that same path. It was harmless (150 KB, no commits) but
  removed with `rm -rf` to avoid a confusing nested git repo inside the
  gitignored dataset folder.

---

## Part B — Exploration, preprocessing, feature engineering

Status: **Complete.**

### Step 6 — Inspect real data formats before writing any code

- **What:** Before writing `preprocess.py`, loaded a few rows from each of
  the four raw sources (Kaggle SQLiV3, CSIC 2010, both CICIDS2017 files,
  one ATRDF `.7z` archive) to see actual column names, label encodings, and
  data quality issues.
- **Why:** The spec's own beginner guidance and the general engineering
  principle of "verify before coding" — guessing column names or label
  schemes for four differently-shaped datasets would have produced a
  preprocessing script full of assumptions that silently fail or
  mislabel data.
- **How:** Used the project's `ml/venv` Python (see Step 5 below) to run
  short inspection snippets against each raw file. Found:
  - Kaggle `SQLiV3.csv` has corrupted rows where unescaped commas in the
    `Sentence` text shift the `Label` value into extra `Unnamed` columns
    (~1% of rows) — these are dropped rather than guessed at.
  - CSIC 2010's `csic_final.csv` has a clean `Class` column (`Valid` /
    `Anomalous`, 36,000 / 25,065 — exactly matching the spec's stated
    counts) plus structured `URI`, `GET-Query`, `POST-Data` columns to
    reconstruct a request payload string from.
  - CICIDS2017's standard "MachineLearningCSV" column set (79 columns) has
    **no Source IP or Timestamp column** — only pre-computed per-flow
    statistics and a `Label` column with a leading space (confirming the
    spec's warning). This is an important limitation: it means true
    per-IP sliding-window features (`requests_per_min_ip`,
    `unique_ip_count_window`) cannot be derived from this file format at
    all.
  - CICIDS2017's Thursday label values contain a mangled character (likely
    an en-dash that became a Unicode replacement character during
    encoding) — matched by substring (`"Brute Force" in label`) rather
    than exact string equality.
  - ATRDF 2023's JSON records are one HTTP request/response pair each,
    with an `Attack_Tag` key present only on malicious requests (its
    absence, not a `False`/`0` value, means benign).

### Step 7 — Set up a Python virtual environment

- **What:** Created `ml/venv` and installed `ml/requirements.txt`.
- **Why:** No Python packages (pandas, scikit-learn, etc.) were installed
  anywhere on the machine yet — needed before any dataset inspection or
  preprocessing code could actually run.
- **How:** `python -m venv ml/venv`, then
  `pip install -r ml/requirements.txt`. First attempt failed:
  `pyarrow==17.0.0` (and other exact-pinned versions in the original
  requirements file) has no prebuilt wheel for Python 3.13, so pip tried
  to build it from source and failed on a missing `pkg_resources`. Fixed
  by relaxing all pins in `ml/requirements.txt` from `==` to `>=`, letting
  pip resolve versions with actual 3.13 wheels (landed on pyarrow 24.0.0,
  pandas 3.0.3, scikit-learn 1.9.0, xgboost 3.3.0).

### Step 8 — Write the canonical feature contract (`ml/features.py`)

- **What:** Defined `CANONICAL_FEATURE_ORDER` (12 payload-level + 5
  flow-level feature names, in a fixed order), `extract_payload_features()`
  (computes all 12 payload features from a request string: length,
  SQL keyword count, quote/dash/semicolon/paren/equals counts, special-char
  ratio, Shannon entropy, and three boolean SQLi-pattern flags), and
  `default_flow_features()` / `default_payload_features()` (explicit
  zero-fill helpers for sources that can't populate one of the two feature
  families).
- **Why:** The spec is explicit that this file and
  `api/middleware/featureExtractor.js` (Phase 3) must produce identical
  feature vectors — defining the contract once, in one place, with the
  order as a named constant, is what makes that possible without drift.
- **How:** Implemented directly in Python using `re` for keyword/pattern
  matching and `collections.Counter` + `math.log2` for Shannon entropy.
  Chose to expose the zero-fill defaults as named functions
  (`default_flow_features()`/`default_payload_features()`) rather than
  inlining `{name: 0.0 for name in ...}` everywhere, so every call site
  documents *why* a family is zero-filled instead of it looking like a bug.

### Step 9 — Write the unification pipeline (`ml/preprocess.py`)

- **What:** One loader function per source
  (`load_kaggle_sqli`, `load_csic`, `load_cicids`, `load_atrdf`), each
  returning a DataFrame in the canonical schema (17 features + `label` +
  `attack_type` + `source`), combined by `build_training_corpus()` (Kaggle +
  CSIC + CICIDS only) and `build_heldout_corpus()` (ATRDF only, all 4
  difficulty levels × train/val splits).
- **Why:** Keeping one function per source (rather than one big branching
  script) makes each source's quirks and label-mapping decisions visible
  and independently testable, and makes the "never mix ATRDF into
  training" rule structurally obvious (it's a separate function, called
  from a separate builder, saved to a separate file).
- **How:** Ran `ml/preprocess.py` end to end three times, finding and
  fixing two real bugs along the way (see below) before trusting the
  output. Final run: `datasets/processed/train.parquet` (677,166 rows) and
  `datasets/processed/heldout_atrdf.parquet` (540,057 rows). Full
  statistics written to `evaluation/results.md`.

#### Bug 1 — post-feature `drop_duplicates()` silently discarded ~99.999% of CICIDS rows

- **What happened:** The first working version of `build_training_corpus()`
  ended with
  `df.drop_duplicates(subset=CANONICAL_FEATURE_ORDER + ["label"])`. Running
  the pipeline produced a training corpus with only **2 CICIDS rows** total
  (expected: hundreds of thousands).
- **Root cause:** CICIDS rows always have all 12 payload features
  zero-filled (network flow data, no request text) and, at the time, 4 of
  5 flow features were also zero-filled (the bug in "Bug 2" below made
  `inter_arrival_time_variance` zero too). So almost every CICIDS row was
  *feature-identical* to every other CICIDS row with the same label —
  `drop_duplicates()` on the engineered feature vectors collapsed them all
  down to essentially one row per label.
- **Fix:** Removed the post-feature dedup entirely. Deduplication of raw,
  near-identical network flow records already happens at the raw-record
  level inside `_clean_cicids()` (a legitimate `drop_duplicates()` on the
  full 79-column raw CICIDS row, before feature engineering collapses
  dimensionality) — a second dedup pass *after* feature engineering was
  simply wrong for a dataset whose engineered feature space is this coarse.
- **Lesson for later phases:** Never deduplicate on an engineered/reduced
  feature vector when the dataset's real information content is much
  higher-dimensional than what got extracted — dedupe raw records, or not
  at all.

#### Bug 2 — leading-space column name mismatch silently zeroed a real feature

- **What happened:** Even after fixing Bug 1, `inter_arrival_time_variance`
  was exactly `0.0` for all 585,492 CICIDS rows (confirmed via `.describe()`
  showing mean/std/max all `0.0`).
- **Root cause:** `_clean_cicids()` strips leading spaces from CICIDS's raw
  column names (e.g. `' Flow IAT Std'` → `'Flow IAT Std'`) before the main
  loop runs. But `_cicids_flow_row()` looked up
  `r.get(" Flow IAT Std", 0.0)` — **with** the leading space — so the
  lookup always missed and silently fell back to the `0.0` default. No
  exception was raised because `.get()` on a pandas Series with a missing
  key just returns the default.
- **Fix:** Changed the lookup key to `"Flow IAT Std"` (no leading space),
  matching the already-stripped column name. Re-ran the pipeline;
  `inter_arrival_time_variance` now has real, widely-spread non-zero
  values (mean ≈ 3.8e13, since the underlying `Flow IAT Std` is in
  microseconds and gets squared — worth normalising/scaling in Phase 4's
  `StandardScaler`, not fixing here).
- **Lesson for later phases:** `.get(key, default)` patterns hide missing-key
  bugs completely — worth spot-checking derived feature columns with
  `.describe()` after any non-trivial preprocessing step, especially when
  a "default" value is a plausible real value (here, `0.0` is a perfectly
  normal variance for a single-packet flow, so the bug didn't look
  obviously wrong at a glance).
