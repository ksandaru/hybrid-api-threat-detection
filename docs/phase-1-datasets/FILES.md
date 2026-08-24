# Phase 1 — Files Created / Modified

All paths relative to the repo root (`hybrid-api-threat-detection/`), unless
noted as outside the project.

## Raw datasets (gitignored — listed here for provenance, not committed)

| Path | Contents | Size (approx) |
|---|---|---|
| `datasets/raw/kaggle_sqliv3/archive.zip` + extracted `SQLiV3.csv`, `sqli.csv`, `sqliv2.csv` | Kaggle SQLi payload strings, labelled | ~7.6 MB extracted |
| `datasets/raw/csic_2010/csic_final.csv` | CSIC 2010 HTTP requests as CSV | ~27 MB |
| `datasets/raw/csic_2010/csic_ecml_final.csv` | Combined CSIC 2010 + ECML/PKDD 2007 CSV | ~40 MB |
| `datasets/raw/csic_2010/original/` | Original raw HTTP request `.txt` files + README + `.tar.gz` | remainder of ~125 MB total |
| `datasets/raw/cicids2017/Tuesday-WorkingHours.pcap_ISCX.csv` | FTP-Patator / SSH-Patator brute force flows | 135.08 MB |
| `datasets/raw/cicids2017/Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv` | Web brute force / XSS / SQLi flows | 52.02 MB |
| `datasets/raw/atrdf_2023/README.md` | ATRDF dataset description, baseline scores | 12 KB |
| `datasets/raw/atrdf_2023/Datasets/dataset_{1,2,3,4}_{train,val}.7z` | Held-out REST API traffic, 4 difficulty levels, `.7z` compressed | ~142 MB combined |

## Outside the project (large one-time clone sources, not project-tracked)

| Path | Contents |
|---|---|
| `repository/Web-Application-Attack-Datasets/` | Full clone of the CSIC 2010 / ECML mirror repo (579 MB) — source for the two CSV copies above |
| `repository/Cisco_Ariel_Uni_API_security_challenge/` | Full clone of the ATRDF 2023 repo (280 MB) — source for the `Datasets/` copy above |

## Processed corpus (gitignored — regenerable via `ml/preprocess.py`)

| Path | Contents | Shape |
|---|---|---|
| `datasets/processed/train.parquet` | Unified Kaggle SQLiV3 + CSIC 2010 + CICIDS2017 corpus, 17 canonical features + label + attack_type + source | 677,166 × 20 |
| `datasets/processed/heldout_atrdf.parquet` | ATRDF 2023, all 4 difficulty levels × train/val — never used in training | 540,057 × 20 |

## Project files created/modified this phase

| File | Purpose |
|---|---|
| `ml/features.py` | Canonical shared feature contract — `CANONICAL_FEATURE_ORDER`, `extract_payload_features()`, `default_flow_features()`/`default_payload_features()`, `shannon_entropy()` |
| `ml/preprocess.py` | Per-source loaders (Kaggle/CSIC/CICIDS/ATRDF), `build_training_corpus()`, `build_heldout_corpus()`, `main()` writing both parquet files |
| `ml/requirements.txt` | Version pins relaxed from `==` to `>=` (see `MEMORY.md` — Python 3.13 wheel availability) |
| `ml/venv/` | Python virtual environment (gitignored, not committed) |
| `evaluation/results.md` | Phase 1 dataset statistics section filled in |

## Project files not yet created

- `ml/notebooks/01_explore.ipynb` (still the Phase 0 stub — see `MEMORY.md`
  "Open items" for why an ad-hoc script was used instead)
