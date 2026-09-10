# legacy/

Material kept for provenance but no longer part of the working system. Nothing
here is referenced by the source, the READMEs, or `docker-compose.yml` — each
item was checked before it was moved.

Deleting this directory does not affect the build, the pipeline, or the tests.

| Path | What it is | Why it moved here |
|---|---|---|
| `presentation/CB016639_Project_Demonstration.pptx` | The live-demo deck used during development | Superseded by the final presentation held outside this repository |
| `notebooks/01_explore.ipynb` | Empty exploration notebook | A stub; exploration ended up in `ml/preprocess.py` |
| `dataset-archives/datasets.zip` | 442 MB bundle of every raw dataset | Built once to move the corpus between machines. The individual files it contains are still in `datasets/raw/` |
| `dataset-archives/kaggle_sqliv3/archive.zip` | Original Kaggle download | Already extracted; the pipeline reads `SQLiV3.csv` |
| `dataset-archives/kaggle_sqliv3/sqli.csv`, `sqliv2.csv` | Earlier versions in the same Kaggle bundle | Only `SQLiV3.csv` is loaded — see `load_kaggle_sqli()` in `ml/preprocess.py` |
| `dataset-archives/csic_2010/csic_ecml_final.csv` | ECML variant of the CSIC corpus | Unused; the pipeline reads `csic_final.csv` |
| `dataset-archives/csic_2010/original/` | Upstream CSIC distribution: raw `.txt` files and a `.tar.gz` | The flattened `csic_final.csv` is what `load_csic()` reads. Kept because it is the closest thing to a primary source, and the original host is no longer reachable |

## What was deliberately *not* moved

| Kept | Reason |
|---|---|
| `datasets/raw/atrdf_2023/Datasets/*.7z` | `load_atrdf()` extracts these on demand — they are the source, and the extracted JSON is the cache |
| `datasets/raw/**/SQLiV3.csv`, `csic_final.csv`, `cicids2017/*.csv` | Direct pipeline inputs |
| `evaluation/traffic_modsec/` | The ModSecurity comparison arm; `compare_configs.py` reads it |
| `docker-compose.yml`, `*/Dockerfile` | The documented deployment path, even though the demonstration runs natively |
| `demo.env`, `.env.example` | Referenced by `README.md` |

## Note on version control

`dataset-archives/` is gitignored — it holds 511 MB of downloaded research data
that should never enter a repository. The other two entries are tracked, and
were moved with `git mv` so their history follows them.
