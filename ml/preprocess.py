"""Dataset cleaning, feature engineering, and corpus unification (Phase 1).

Produces:
  - datasets/processed/train.parquet       (Kaggle SQLiV3 + CSIC 2010 + CICIDS2017)
  - datasets/processed/heldout_atrdf.parquet (ATRDF 2023 — NEVER used for training)

Both files share the same schema: the 17 canonical features from
ml/features.py, plus `label` (0 benign / 1 attack), `attack_type`
(none/sqli/brute_force/credential_stuffing), and `source` (provenance).

Train/test splitting and SMOTE are deliberately NOT done here — that is
ml/train.py's job (Phase 4), operating on the unsplit corpus this script
produces. See docs/phase-1-datasets/IMPLEMENTATION.md for why.

Known limitations (see docs/phase-1-datasets/MEMORY.md for full detail):
  - CICIDS2017's standard "MachineLearningCSV" format has no Source IP or
    Timestamp columns, so `requests_per_min_ip`, `distinct_usernames_tried`,
    and `unique_ip_count_window` cannot be derived from it and are
    zero-filled. `inter_arrival_time_variance` IS derived, from the
    dataset's own Flow IAT Std column. Real values for all five flow
    features only exist at live inference time (Phase 3 middleware).
  - CICIDS2017 has no genuine credential-stuffing-labelled traffic (that
    requires known leaked credential replay, which this project generates
    itself in Phase 8) — the training corpus has zero credential_stuffing
    examples. It is a real, drop-in class the API can be attacked with in
    Phase 8/9, but the offline model won't have seen labelled examples of
    it unless synthetic traffic is folded back into retraining later.
  - CSIC 2010's "Anomalous" class covers multiple attack styles (SQLi,
    XSS, buffer overflow, CRLF injection, parameter tampering, etc.), not
    only SQLi. Per the spec's framing of CSIC as an SQLi/web-attack payload
    source, all Anomalous rows are labelled attack_type="sqli" here as a
    documented simplification.
  - CICIDS2017's Web Attack - XSS rows don't map to any of this project's
    three target attack types (SQLi, brute force, credential stuffing) and
    are excluded from the unified corpus (kept out, not mislabelled).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from features import (
    CANONICAL_FEATURE_ORDER,
    default_flow_features,
    default_payload_features,
    extract_payload_features,
)

RAW_DIR = Path(__file__).parent.parent / "datasets" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "datasets" / "processed"


def _row_from_payload(text, label, attack_type, source):
    row = default_flow_features()
    row.update(extract_payload_features(text))
    row["label"] = label
    row["attack_type"] = attack_type
    row["source"] = source
    return row


def load_kaggle_sqli() -> pd.DataFrame:
    """Kaggle SQLiV3.csv — payload strings labelled 0 (benign) / 1 (SQLi).

    The raw CSV has known parsing corruption: some Sentence values contain
    unescaped commas, which shift the Label value into extra "Unnamed"
    columns. Rows where Label doesn't coerce to 0/1 are dropped (~1% of
    rows) rather than guessed at.
    """
    path = RAW_DIR / "kaggle_sqliv3" / "SQLiV3.csv"
    df = pd.read_csv(path, encoding_errors="ignore", on_bad_lines="skip")
    label = pd.to_numeric(df["Label"], errors="coerce")
    valid = label.isin([0, 1])
    df = df.loc[valid].copy()
    label = label.loc[valid].astype(int)

    rows = []
    for text, lbl in zip(df["Sentence"], label):
        attack_type = "sqli" if lbl == 1 else "none"
        rows.append(_row_from_payload(text, lbl, attack_type, "kaggle_sqliv3"))
    return pd.DataFrame(rows)


def load_csic() -> pd.DataFrame:
    """CSIC 2010 — reconstruct a request payload string from URI + query +
    POST body, labelled from the Class column (Valid=0, Anomalous=1)."""
    path = RAW_DIR / "csic_2010" / "csic_final.csv"
    df = pd.read_csv(path, encoding_errors="ignore", on_bad_lines="skip")

    def build_text(r):
        parts = [str(r.get("URI", "") or "")]
        if pd.notna(r.get("GET-Query")):
            parts.append(str(r["GET-Query"]))
        if pd.notna(r.get("POST-Data")):
            parts.append(str(r["POST-Data"]))
        return " ".join(parts)

    rows = []
    for _, r in df.iterrows():
        lbl = 0 if r["Class"] == "Valid" else 1
        attack_type = "sqli" if lbl == 1 else "none"
        rows.append(_row_from_payload(build_text(r), lbl, attack_type, "csic_2010"))
    return pd.DataFrame(rows)


def _cicids_flow_row(r, label, attack_type, source):
    row = default_payload_features()
    iat_std = r.get("Flow IAT Std", 0.0)
    iat_std = 0.0 if pd.isna(iat_std) else float(iat_std)
    row.update(
        {
            "requests_per_min_ip": 0.0,  # not derivable — see module docstring
            "login_failure_ratio": 0.0,  # not derivable — see module docstring
            "inter_arrival_time_variance": iat_std ** 2,
            "distinct_usernames_tried": 0.0,  # not derivable — see module docstring
            "unique_ip_count_window": 0.0,  # not derivable — see module docstring
        }
    )
    row["label"] = label
    row["attack_type"] = attack_type
    row["source"] = source
    return row


def _clean_cicids(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=["Flow IAT Std", "Label"])
    df = df.drop_duplicates()
    return df


def load_cicids() -> pd.DataFrame:
    """CICIDS2017 Tuesday (FTP/SSH brute force) + Thursday morning (web
    attacks). Only rows matching this project's three target attack types
    (plus benign) are kept — Web Attack / XSS rows are excluded since XSS
    is out of scope for this project."""
    tuesday = _clean_cicids(
        pd.read_csv(
            RAW_DIR / "cicids2017" / "Tuesday-WorkingHours.pcap_ISCX.csv",
            encoding_errors="ignore",
        )
    )
    thursday = _clean_cicids(
        pd.read_csv(
            RAW_DIR / "cicids2017" / "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv",
            encoding_errors="ignore",
        )
    )

    rows = []
    for _, r in tuesday.iterrows():
        label_raw = str(r["Label"])
        if label_raw == "BENIGN":
            rows.append(_cicids_flow_row(r, 0, "none", "cicids2017_tuesday"))
        elif "Patator" in label_raw:
            rows.append(_cicids_flow_row(r, 1, "brute_force", "cicids2017_tuesday"))

    for _, r in thursday.iterrows():
        label_raw = str(r["Label"]).encode("ascii", "ignore").decode()
        if label_raw == "BENIGN":
            rows.append(_cicids_flow_row(r, 0, "none", "cicids2017_thursday"))
        elif "Brute Force" in label_raw:
            rows.append(_cicids_flow_row(r, 1, "brute_force", "cicids2017_thursday"))
        elif "Sql Injection" in label_raw:
            rows.append(_cicids_flow_row(r, 1, "sqli", "cicids2017_thursday"))
        # "Web Attack  XSS" rows intentionally excluded (out of scope)

    return pd.DataFrame(rows)


ATTACK_TAG_MAP = {
    "SQL Injection": "sqli",
}


def load_atrdf(dataset_num: int = 1, split: str = "train") -> pd.DataFrame:
    """ATRDF 2023 held-out dataset. NEVER call this from the training
    corpus builder — only from the heldout builder below."""
    import json
    import subprocess

    archive = RAW_DIR / "atrdf_2023" / "Datasets" / f"dataset_{dataset_num}_{split}.7z"
    extract_dir = RAW_DIR / "atrdf_2023" / "Datasets" / f"dataset_{dataset_num}_{split}"
    json_path = extract_dir / f"dataset_{dataset_num}_{split}.json"

    if not json_path.exists():
        sevenzip = r"C:\Program Files\7-Zip\7z.exe"
        subprocess.run(
            [sevenzip, "x", "-y", f"-o{extract_dir}", str(archive)],
            check=True,
            capture_output=True,
        )

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for item in data:
        req = item["request"]
        text = f"{req.get('url', '')} {req.get('body', '')}"
        tag = req.get("Attack_Tag")
        if tag is None:
            rows.append(_row_from_payload(text, 0, "none", f"atrdf_2023_ds{dataset_num}"))
        else:
            attack_type = ATTACK_TAG_MAP.get(tag, "other")
            rows.append(_row_from_payload(text, 1, attack_type, f"atrdf_2023_ds{dataset_num}"))
    return pd.DataFrame(rows)


def build_training_corpus() -> pd.DataFrame:
    """Combine all three sources. Deduplication happens per-source, at the
    raw-record level (see _clean_cicids, and Kaggle/CSIC's own on_bad_lines
    handling) — NOT on the engineered feature vectors here. CICIDS rows
    legitimately collapse to few distinct values across most of the 17
    canonical features (payload features are always zero-filled for flow
    sources, and 4 of 5 flow features are zero-filled too — see module
    docstring), so a post-feature dedup would silently discard the vast
    majority of CICIDS training examples.
    """
    parts = [load_kaggle_sqli(), load_csic(), load_cicids()]
    df = pd.concat(parts, ignore_index=True)
    return df[CANONICAL_FEATURE_ORDER + ["label", "attack_type", "source"]]


def build_heldout_corpus() -> pd.DataFrame:
    parts = [load_atrdf(dataset_num=n, split="train") for n in (1, 2, 3, 4)]
    parts += [load_atrdf(dataset_num=n, split="val") for n in (1, 2, 3, 4)]
    df = pd.concat(parts, ignore_index=True)
    return df[CANONICAL_FEATURE_ORDER + ["label", "attack_type", "source"]]


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Building training corpus (Kaggle SQLiV3 + CSIC 2010 + CICIDS2017)...")
    train_df = build_training_corpus()
    train_path = PROCESSED_DIR / "train.parquet"
    train_df.to_parquet(train_path, index=False)
    print(f"  saved {train_path} — shape {train_df.shape}")
    print(train_df["source"].value_counts())
    print(train_df["attack_type"].value_counts())

    print("\nBuilding held-out ATRDF 2023 corpus (never used for training)...")
    heldout_df = build_heldout_corpus()
    heldout_path = PROCESSED_DIR / "heldout_atrdf.parquet"
    heldout_df.to_parquet(heldout_path, index=False)
    print(f"  saved {heldout_path} — shape {heldout_df.shape}")
    print(heldout_df["attack_type"].value_counts())


if __name__ == "__main__":
    main()
