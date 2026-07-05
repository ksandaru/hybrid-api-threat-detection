# Datasets

Raw and processed datasets are intentionally gitignored. Keep only lightweight
provenance notes in Git; never commit downloaded archives, extracted CSVs, or
generated Parquet files.

## Expected Local Layout

Place the public research datasets in these paths before running
`ml/preprocess.py`:

```text
datasets/
  raw/
    kaggle_sqliv3/
      SQLiV3.csv
    csic_2010/
      csic_final.csv
    cicids2017/
      Tuesday-WorkingHours.pcap_ISCX.csv
      Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv
    atrdf_2023/
      Datasets/
        dataset_1_train.7z
        dataset_1_val.7z
        dataset_2_train.7z
        dataset_2_val.7z
        dataset_3_train.7z
        dataset_3_val.7z
        dataset_4_train.7z
        dataset_4_val.7z
  processed/
    train.parquet
    heldout_atrdf.parquet
```

`train.parquet` is generated from Kaggle SQLiV3, CSIC 2010, and CICIDS2017.
`heldout_atrdf.parquet` is generated from ATRDF 2023 and must remain a held-out
cross-dataset evaluation set.

## Rebuild

From the repository root:

```powershell
.\ml\venv\Scripts\python ml\preprocess.py
```

The ATRDF extractor currently expects 7-Zip at
`C:\Program Files\7-Zip\7z.exe` when the JSON files have not already been
extracted.

## Training Boundary

Do not train on ATRDF 2023. It is reserved for Phase 9 cross-dataset
evaluation only.
