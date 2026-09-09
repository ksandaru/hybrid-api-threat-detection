"""
Phase 9 - offline comparative evaluation.

Answers three questions the dissertation needs evidence for:

1. How do the individual models and the combined pipeline perform on the
   internal test split? (Reproduces the Phase 4/5 figures independently of
   train.py, from the saved artefacts, so the numbers can be regenerated
   without retraining.)

2. **How much performance is lost on data from a completely different
   source?** The ATRDF 2023 corpus was never trained on, never validated
   against, and never used to select the threshold. Evaluating on it is the
   only honest test of whether this generalises beyond the data it learned
   from, and the drop against the internal test split is the headline result
   of this phase.

3. Which configuration is actually better? The live-traffic comparison of
   rule-only / ML-only / hybrid lives in evaluation/compare_configs.py,
   because it needs the recorded per-request scores rather than the corpus.

Nothing here retrains anything. It loads the artefacts that ml/train.py
produced and reads the same operating point the inference service uses, so
what is measured is what is deployed.

Run:
    ml/venv/Scripts/python.exe ml/evaluate.py
    ml/venv/Scripts/python.exe ml/evaluate.py --no-figures
"""

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score,
                             roc_curve)
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).parent))
from features import CANONICAL_FEATURE_ORDER  # noqa: E402

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "datasets" / "processed" / "train.parquet"
HELDOUT = ROOT / "datasets" / "processed" / "heldout_atrdf.parquet"
MODEL_DIR = ROOT / "ml" / "models"
FIG_DIR = ROOT / "evaluation" / "figures"
OUT_JSON = ROOT / "evaluation" / "phase9_offline.json"

SEED = 42
PAYLOAD_SOURCES = ("kaggle_sqliv3", "csic_2010")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------ metrics
def metrics(y_true, y_pred, y_score=None):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "n": int(len(y_true)),
    }
    if y_score is not None and len(np.unique(y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, y_score))
    return out


def fmt(m):
    auc = f" auc={m['roc_auc']:.4f}" if "roc_auc" in m else ""
    return (f"acc={m['accuracy']:.4f} prec={m['precision']:.4f} "
            f"rec={m['recall']:.4f} f1={m['f1']:.4f} fpr={m['fpr']:.4f}{auc}")


# ------------------------------------------------------------------ artefacts
class Pipeline:
    """The deployed scoring pipeline, rebuilt from the saved artefacts."""

    def __init__(self):
        meta = json.loads((MODEL_DIR / "feature_order.json").read_text(encoding="utf-8"))
        self.order = meta["feature_order"]
        op = meta.get("operating_point") or {}
        w = op.get("weights") or {}
        self.w_rf = float(w.get("random_forest", 0.4))
        self.w_xgb = float(w.get("xgboost", 0.4))
        self.w_iso = float(w.get("isolation_forest", 0.2))
        self.threshold = float(op.get("selected_threshold", 0.5))
        cal = meta.get("iso_calibration") or {}
        self.iso_p1 = float(cal.get("p1", 0.0))
        self.iso_p99 = float(cal.get("p99", 1.0))

        self.rf = joblib.load(MODEL_DIR / "random_forest.pkl")
        self.xgb = joblib.load(MODEL_DIR / "xgboost.pkl")
        self.iso = joblib.load(MODEL_DIR / "isolation_forest.pkl")
        self.scaler = joblib.load(MODEL_DIR / "scaler.pkl")

    def scale(self, X):
        return self.scaler.transform(X)

    def per_model(self, Xs):
        p_rf = self.rf.predict_proba(Xs)[:, 1]
        p_xgb = self.xgb.predict_proba(Xs)[:, 1]
        raw = -self.iso.score_samples(Xs)
        span = max(self.iso_p99 - self.iso_p1, 1e-9)
        p_iso = np.clip((raw - self.iso_p1) / span, 0, 1)
        return p_rf, p_xgb, p_iso

    def combined(self, p_rf, p_xgb, p_iso):
        return self.w_rf * p_rf + self.w_xgb * p_xgb + self.w_iso * p_iso


# ------------------------------------------------------------------ data
def load_test_split():
    """Reproduce train.py's split exactly, so 'test' means the same rows."""
    df = pd.read_parquet(CORPUS)
    X = df[CANONICAL_FEATURE_ORDER].astype("float64").values
    y = df["label"].astype(int).values
    src = df["source"].values

    idx = np.arange(len(y))
    ifit, ite = train_test_split(idx, test_size=0.2, stratify=y, random_state=SEED)
    # (train/validation split reproduced only so the indices line up with train.py)
    train_test_split(ifit, test_size=0.15, stratify=y[ifit], random_state=SEED)
    return X[ite], y[ite], src[ite]


def load_heldout():
    df = pd.read_parquet(HELDOUT)
    X = df[CANONICAL_FEATURE_ORDER].astype("float64").values
    y = df["label"].astype(int).values
    src = df["source"].values if "source" in df.columns else np.array(["atrdf"] * len(y))
    return X, y, src


# ------------------------------------------------------------------ figures
def figures(store):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
    BLUE, ORANGE, GREEN, GREY = "#1F4E79", "#C55A11", "#375623", "#808080"

    # --- 1. ROC curves: internal test vs held-out -----------------------
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    for ax, key, title in [
        (axes[0], "test", "Internal test split (135,434 rows)"),
        (axes[1], "heldout", "Held-out ATRDF 2023 (540,057 rows)"),
    ]:
        d = store[key]
        for name, colour in [("random_forest", BLUE), ("xgboost", ORANGE),
                             ("isolation_forest", GREEN), ("combined", "#000000")]:
            fpr, tpr = d["roc"][name]
            auc = d["models"][name].get("roc_auc", float("nan"))
            ax.plot(fpr, tpr, color=colour, linewidth=1.4,
                    label=f"{name.replace('_', ' ')} (AUC {auc:.3f})")
        ax.plot([0, 1], [0, 1], color=GREY, linestyle="--", linewidth=0.8)
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.set_title(title, fontsize=10)
        ax.legend(loc="lower right", fontsize=7.5, frameon=False)
        ax.grid(alpha=0.25, linewidth=0.5)
    fig.suptitle("ROC curves: generalisation to an unseen dataset", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "roc_test_vs_heldout.png", bbox_inches="tight")
    plt.close(fig)

    # --- 2. Confusion matrices for the combined pipeline ----------------
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6))
    for ax, key, title in [
        (axes[0], "test", "Internal test split"),
        (axes[1], "heldout", "Held-out ATRDF 2023"),
    ]:
        m = store[key]["models"]["combined"]
        cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]], dtype=float)
        cmn = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{int(cm[i, j]):,}\n({cmn[i, j]:.1%})",
                        ha="center", va="center", fontsize=8.5,
                        color="white" if cmn[i, j] > 0.5 else "black")
        ax.set_xticks([0, 1], ["Predicted\nbenign", "Predicted\nattack"])
        ax.set_yticks([0, 1], ["Actual\nbenign", "Actual\nattack"])
        ax.set_title(title, fontsize=10)
    fig.suptitle("Combined pipeline confusion matrices (threshold 0.77)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "confusion_matrices.png", bbox_inches="tight")
    plt.close(fig)

    # --- 3. Feature importance -----------------------------------------
    imp = store["importances"]
    names = list(imp.keys())[:12]
    vals = [imp[n] for n in names]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    colours = [BLUE if v > 0.001 else "#C00000" for v in vals]
    ax.barh(range(len(names))[::-1], vals, color=colours, height=0.68)
    ax.set_yticks(range(len(names))[::-1], names, fontsize=8)
    ax.set_xlabel("Random Forest feature importance")
    ax.grid(axis="x", alpha=0.25, linewidth=0.5)
    for i, v in enumerate(vals):
        ax.text(v + 0.004, len(names) - 1 - i, f"{v:.4f}", va="center", fontsize=7.5)
    ax.set_title("Learned importance: statistical texture, not keywords", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "feature_importance.png", bbox_inches="tight")
    plt.close(fig)

    # --- 4. Generalisation drop ----------------------------------------
    keys = ["accuracy", "precision", "recall", "f1"]
    t = [store["test"]["models"]["combined"][k] for k in keys]
    h = [store["heldout"]["models"]["combined"][k] for k in keys]
    x = np.arange(len(keys)); wdt = 0.36
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    b1 = ax.bar(x - wdt / 2, t, wdt, label="Internal test split", color=BLUE)
    b2 = ax.bar(x + wdt / 2, h, wdt, label="Held-out ATRDF 2023", color=ORANGE)
    for bars in (b1, b2):
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015,
                    f"{b.get_height():.3f}", ha="center", fontsize=7.5)
    ax.set_xticks(x, [k.capitalize() for k in keys])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Score")
    ax.legend(frameon=False, fontsize=8.5)
    ax.grid(axis="y", alpha=0.25, linewidth=0.5)
    ax.set_title("Cross-dataset generalisation of the combined pipeline", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "generalisation_drop.png", bbox_inches="tight")
    plt.close(fig)

    log(f"figures written to {FIG_DIR}")


# ------------------------------------------------------------------ main
def evaluate_split(pipe, X, y, src, label):
    log(f"scoring {label}: {X.shape[0]:,} rows")
    Xs = pipe.scale(X)
    t0 = time.time()
    p_rf, p_xgb, p_iso = pipe.per_model(Xs)
    comb = pipe.combined(p_rf, p_xgb, p_iso)
    log(f"  scored in {time.time() - t0:.1f}s")

    out = {"models": {}, "roc": {}}
    scores = {
        "random_forest": (p_rf, 0.5),
        "xgboost": (p_xgb, 0.5),
        "isolation_forest": (p_iso, 0.5),
        "combined": (comb, pipe.threshold),
    }
    for name, (sc, th) in scores.items():
        pred = (sc >= th).astype(int)
        m = metrics(y, pred, sc)
        m["threshold"] = th
        out["models"][name] = m
        fpr, tpr, _ = roc_curve(y, sc)
        # thin the curve so the JSON stays small; figures are unaffected visually
        step = max(1, len(fpr) // 2000)
        out["roc"][name] = (fpr[::step].tolist(), tpr[::step].tolist())
        log(f"  {name:18} {fmt(m)}")

    # payload-bearing subset, where a payload model is meaningful
    pay = np.isin(src, PAYLOAD_SOURCES)
    if pay.any():
        pred = (comb >= pipe.threshold).astype(int)
        out["combined_payload_only"] = metrics(y[pay], pred[pay], comb[pay])
        log(f"  {'combined (payload)':18} {fmt(out['combined_payload_only'])}")

    # per-source breakdown
    out["per_source"] = {}
    for s in sorted(set(src.tolist())):
        sel = src == s
        if sel.sum() < 50:
            continue
        pred = (comb >= pipe.threshold).astype(int)
        out["per_source"][str(s)] = metrics(y[sel], pred[sel])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    log("loading artefacts")
    pipe = Pipeline()
    log(f"  weights rf={pipe.w_rf} xgb={pipe.w_xgb} iso={pipe.w_iso} "
        f"threshold={pipe.threshold}")

    store = {"threshold": pipe.threshold,
             "weights": {"random_forest": pipe.w_rf, "xgboost": pipe.w_xgb,
                         "isolation_forest": pipe.w_iso}}

    Xte, yte, ste = load_test_split()
    store["test"] = evaluate_split(pipe, Xte, yte, ste, "internal test split")

    Xh, yh, sh = load_heldout()
    store["heldout"] = evaluate_split(pipe, Xh, yh, sh, "held-out ATRDF 2023")

    store["importances"] = dict(sorted(
        zip(CANONICAL_FEATURE_ORDER, pipe.rf.feature_importances_.astype(float)),
        key=lambda kv: -kv[1]))

    # headline: the generalisation drop
    a, b = store["test"]["models"]["combined"], store["heldout"]["models"]["combined"]
    store["generalisation_drop"] = {
        k: {"test": a[k], "heldout": b[k], "delta": b[k] - a[k]}
        for k in ("accuracy", "precision", "recall", "f1", "fpr")
    }

    print("\n" + "=" * 76)
    print("CROSS-DATASET GENERALISATION - combined pipeline")
    print("=" * 76)
    print(f"{'metric':<12}{'internal test':>16}{'held-out ATRDF':>18}{'change':>14}")
    for k, v in store["generalisation_drop"].items():
        print(f"{k:<12}{v['test']:>16.4f}{v['heldout']:>18.4f}{v['delta']:>+14.4f}")

    if not args.no_figures:
        figures(store)

    # strip ROC arrays before writing - they are only needed for the figures
    slim = json.loads(json.dumps(store))
    for k in ("test", "heldout"):
        slim[k].pop("roc", None)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    log(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
