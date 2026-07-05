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

## Project files not yet created

- `ml/notebooks/01_explore.ipynb` (still the Phase 0 stub)
- `ml/preprocess.py`, `ml/features.py` (still Phase 0 stubs)
- `datasets/processed/train.parquet`, `datasets/processed/heldout_atrdf.parquet`
- Dataset statistics section in `evaluation/results.md`
