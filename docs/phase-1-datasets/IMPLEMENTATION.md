# Phase 1 — Implementation Log

Status: **In progress** — all four raw datasets acquired; exploration,
preprocessing, feature engineering, and the unified parquet corpus are not
yet built.

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

Status: **Not started yet.** To be filled in as this work happens:
`ml/notebooks/01_explore.ipynb`, `ml/preprocess.py`, `ml/features.py`,
`datasets/processed/train.parquet`, `datasets/processed/heldout_atrdf.parquet`.
