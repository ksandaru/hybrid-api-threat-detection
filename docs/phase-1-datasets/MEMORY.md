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

## Open items for the rest of Phase 1

- `ml/notebooks/01_explore.ipynb` exploration not yet done for any dataset.
- `ml/preprocess.py` / `ml/features.py` not yet implemented — the canonical
  feature contract still needs to be defined once and mirrored later in
  `api/middleware/featureExtractor.js` (Phase 3).
- `datasets/processed/train.parquet` and `heldout_atrdf.parquet` don't
  exist yet.
- Dataset statistics for `evaluation/results.md` not yet written.
