# Phase 1 — Memory (decisions, gotchas, lessons)

## Decisions made (and why)

- **Manual clone for large/one-time sources, AI handles the rest.** For
  CSIC 2010 and ATRDF 2023, the source repos are large (579 MB and 280 MB)
  and one-time downloads. Rather than the AI repeatedly retrying slow
  `git clone` operations through its own tool timeout, the project owner
  cloned these themselves outside the project directory, and the AI copied
  only the specific files needed into `datasets/raw/`. This is faster and
  avoids bloating the AI's working directory with a full second copy of
  git history for data that's gitignored anyway.
- **Kaggle mirror over UNB's own form-gated download for CICIDS2017.** The
  official UNB source works but is gated behind a registration form with
  an unclear-progress download afterward. A CC0-licensed, byte-identical
  mirror on Kaggle (`chethuhn/network-intrusion-dataset`) was found and
  used instead, since the project owner was already authenticated there and
  it supports downloading individual daily files rather than the whole ~800
  MB set. The official UNB source remains documented in `datasets/README.md`
  as the canonical citation for the dissertation, even though the actual
  bytes came from the Kaggle mirror.
- **Kept the raw `.7z` ATRDF archives, extracted only one to test.** Didn't
  bulk-extract all 8 ATRDF archives during acquisition — only
  `dataset_1_train.7z` was test-extracted to confirm the format is
  readable. Full extraction belongs in `ml/preprocess.py`, not the
  acquisition step.

## Gotchas encountered

- **Browser automation tool blocks `github.com` and `unb.ca`/`cicresearch.ca`
  navigation.** The Chrome extension's domain allowlist prevented
  `mcp__claude-in-chrome__navigate` from reaching these domains directly
  (returned "Navigation to this domain is not allowed"). Worked around by
  using direct `git clone`/`curl` from the command line for GitHub sources,
  and by asking the project owner to use their own regular browser for the
  CICIDS2017 registration form.
- **`git clone --depth 1` can still time out on large repos.** Even a
  shallow clone of `msudol/Web-Application-Attack-Datasets` (579 MB total)
  exceeded the 2-minute command timeout. `--depth 1` limits history, not
  working-tree size — large binary/data files in the repo still have to be
  fully downloaded. For any future large-repo source, either raise the
  timeout up front, or download the specific file via `raw.githubusercontent.com`
  instead of cloning.
- **UNB's direct file URLs don't bypass the registration form.** Testing
  `http://205.174.165.80/CICDataset/...` and the `https://cicresearch.ca/...`
  equivalent both redirect back to a generic index page unless a valid
  session (established by submitting the form) exists — there is no
  unauthenticated direct-download path.

## Process lesson (carried over from Phase 0)

- After the rejected unattended `git clone` for ATRDF, all subsequent
  downloads (Kaggle files, dataset copies) were preceded by an explicit
  confirmation question naming the exact file, source, and size before the
  action was taken. This should continue for Phase 1's remaining work
  (e.g. if additional CICIDS days or datasets are added later).

## Decisions made during preprocessing (and why)

- **Relaxed exact version pins in `ml/requirements.txt` to `>=`.** The
  original pins (`pyarrow==17.0.0` etc.) predate Python 3.13 wheel
  availability and failed to install. Using `>=` let pip resolve versions
  that actually have 3.13 wheels. The resolved versions are recorded in
  `evaluation/results.md`/this file for reproducibility:
  pyarrow 24.0.0, pandas 3.0.3, scikit-learn 1.9.0, xgboost 3.3.0.
- **CSIC 2010's "Anomalous" class → all mapped to `attack_type="sqli"`.**
  CSIC actually contains multiple attack styles (XSS, buffer overflow, CRLF
  injection, parameter tampering, not just SQLi), but the spec frames CSIC
  as an SQLi/web-attack payload source alongside Kaggle, and this project's
  `attack_type` schema has no generic "web_attack" bucket. Documented as a
  deliberate simplification, not an oversight.
  See also [[phase-4-train-ml-models]] — if SQLi precision/recall look odd
  in training, this label simplification is the first place to check.
- **CICIDS2017 Web Attack / XSS rows excluded from the training corpus.**
  XSS isn't one of this project's three target attack types (SQLi, brute
  force, credential stuffing), so those rows are dropped rather than
  mislabelled into an existing bucket.
- **No credential-stuffing examples in the offline training corpus.** None
  of the four sources contain genuine leaked-credential-replay traffic.
  This is a real, stated limitation — the model will only ever see
  credential-stuffing examples if Phase 8's synthetic
  `credential_stuffing.py` traffic is captured and folded back into
  retraining. Flagged clearly in `evaluation/results.md` so it isn't
  mistaken for an oversight when interpreting Phase 9 results for that
  attack type.
- **Train/test split and SMOTE deliberately NOT done in `preprocess.py`.**
  The spec lists SMOTE under both Phase 1 and Phase 4's task lists;
  interpreted this as Phase 1 producing the full unsplit, cleaned,
  labelled corpus, and Phase 4's `train.py` owning the actual
  train/test split + SMOTE (since SMOTE must only ever touch a training
  split, never data that might end up in a test split).

## Gotchas encountered

- **Browser automation tool blocks `github.com` and `unb.ca`/`cicresearch.ca`
  navigation.** The Chrome extension's domain allowlist prevented
  `mcp__claude-in-chrome__navigate` from reaching these domains directly
  (returned "Navigation to this domain is not allowed"). Worked around by
  using direct `git clone`/`curl` from the command line for GitHub sources,
  and by asking the project owner to use their own regular browser for the
  CICIDS2017 registration form.
- **`git clone --depth 1` can still time out on large repos.** Even a
  shallow clone of `msudol/Web-Application-Attack-Datasets` (579 MB total)
  exceeded the 2-minute command timeout. `--depth 1` limits history, not
  working-tree size — large binary/data files in the repo still have to be
  fully downloaded. For any future large-repo source, either raise the
  timeout up front, or download the specific file via `raw.githubusercontent.com`
  instead of cloning.
- **UNB's direct file URLs don't bypass the registration form.** Testing
  `http://205.174.165.80/CICDataset/...` and the `https://cicresearch.ca/...`
  equivalent both redirect back to a generic index page unless a valid
  session (established by submitting the form) exists — there is no
  unauthenticated direct-download path.
- **`pip install -r requirements.txt` failed on exact-pinned `pyarrow==17.0.0`
  under Python 3.13** — no prebuilt wheel existed for that version/Python
  combination, so pip fell back to a source build that failed on a missing
  `pkg_resources`. Fixed by relaxing pins to `>=` (see Decisions above).
- **Post-feature-engineering `drop_duplicates()` silently discarded almost
  all CICIDS training rows**, and **a leading-space key mismatch
  (`" Flow IAT Std"` vs. the already-stripped `"Flow IAT Std"`) silently
  zeroed a real feature column.** Both are documented in full, with root
  cause and fix, in `IMPLEMENTATION.md` Part B (Bug 1 and Bug 2) — worth
  reading before touching `ml/preprocess.py` again, since both bugs
  produced *no error at all*, only quietly wrong data that needed
  `.describe()`/`.value_counts()` sanity checks to notice.

## Process lesson (carried over from Phase 0)

- After the rejected unattended `git clone` for ATRDF, all subsequent
  downloads (Kaggle files, dataset copies) were preceded by an explicit
  confirmation question naming the exact file, source, and size before the
  action was taken.
- **Silent-failure patterns are the real risk in data pipelines, not
  crashes.** Both Phase 1 bugs (dedup collapse, key mismatch) ran to
  completion without any error or warning — they were only caught by
  actively sanity-checking output shapes and `.describe()` statistics
  against expectations, not by the code "working." Apply the same
  scrutiny in Phase 4 (model training) and Phase 9 (evaluation) — a
  suspiciously clean or suspiciously perfect result is a bug signal, per
  the spec's own note about 100% accuracy indicating leakage.

## Open items for the rest of the project

- `ml/notebooks/01_explore.ipynb` was not filled in as an executed
  notebook — the equivalent exploration was done via ad-hoc scripts while
  building `preprocess.py`. If a supervisor specifically wants an
  executed `.ipynb`, it can be reconstructed from the loader functions in
  `ml/preprocess.py` plus the `.describe()`/`.value_counts()` calls used
  during debugging (see `IMPLEMENTATION.md` Steps 6-9).
- ATRDF's `.7z` archives are extracted on demand by `load_atrdf()` (calls
  7-Zip via `subprocess`) rather than pre-extracted — this means the first
  run of `preprocess.py` after a fresh clone will take longer while it
  extracts all 8 archives.
