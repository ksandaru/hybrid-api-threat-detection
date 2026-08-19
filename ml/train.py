"""Model training (Phase 4).

Trains the three models named in the methodology and saves them, together with
the fitted scaler and the canonical feature ordering, to ml/models/.

  Random Forest     supervised, primary classifier, exposes feature importance
  XGBoost           supervised, gradient boosting
  Isolation Forest  unsupervised, fitted on benign traffic only

Ordering discipline (this is the part that is easy to get wrong):

  1. split first, stratified, so the class balance is preserved on both sides
  2. fit the scaler on the training split only
  3. apply SMOTE to the training split only, and only after the split

Applying SMOTE before the split would interpolate synthetic minority samples
between rows that later land on opposite sides of it, so the model would be
evaluated partly on relatives of data it had already seen. Cross-validation
runs SMOTE inside each fold, via an imbalanced-learn pipeline, for the same
reason: resampling the whole training set before cross-validating leaks between
folds.

Usage:
    python ml/train.py                 full corpus, with cross-validation
    python ml/train.py --no-cv         skip cross-validation (much faster)
    python ml/train.py --sample 50000  stratified subsample, for a smoke run
    python ml/train.py --sources kaggle_sqliv3
"""

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).parent))
from features import CANONICAL_FEATURE_ORDER

ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "datasets" / "processed" / "train.parquet"
MODEL_DIR = ROOT / "ml" / "models"
RESULTS = ROOT / "evaluation" / "results.md"

SEED = 42


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def binary_metrics(y_true, y_pred, y_score=None):
    """Accuracy, precision, recall, F1 and false positive rate.

    FPR is reported explicitly because it is the metric that decides whether an
    inline control is deployable, and it is the one accuracy hides when the
    negative class dominates.
    """
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }
    if y_score is not None:
        try:
            out["roc_auc"] = roc_auc_score(y_true, y_score)
        except ValueError:
            out["roc_auc"] = float("nan")
    return out


def fmt(m):
    auc = f" auc={m['roc_auc']:.4f}" if "roc_auc" in m else ""
    return (
        f"acc={m['accuracy']:.4f} prec={m['precision']:.4f} rec={m['recall']:.4f} "
        f"f1={m['f1']:.4f} fpr={m['fpr']:.4f}{auc}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cv", action="store_true", help="skip cross-validation")
    ap.add_argument("--sample", type=int, default=0, help="stratified subsample size")
    ap.add_argument("--sources", nargs="*", default=None, help="restrict to these source values")
    args = ap.parse_args()

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    log(f"loading {CORPUS}")
    df = pd.read_parquet(CORPUS)
    log(f"corpus {df.shape}")

    if args.sources:
        df = df[df["source"].isin(args.sources)].reset_index(drop=True)
        log(f"restricted to {args.sources}: {df.shape}")

    if args.sample and args.sample < len(df):
        df, _ = train_test_split(
            df, train_size=args.sample, stratify=df["label"], random_state=SEED
        )
        df = df.reset_index(drop=True)
        log(f"subsampled to {df.shape}")

    X = df[CANONICAL_FEATURE_ORDER].astype("float64").values
    y = df["label"].astype(int).values
    source = df["source"].values

    counts = np.bincount(y)
    log(f"class balance benign={counts[0]:,} attack={counts[1]:,} "
        f"ratio={counts[0] / max(counts[1], 1):.1f}:1")

    # 1. split first
    idx = np.arange(len(y))
    itr, ite = train_test_split(idx, test_size=0.2, stratify=y, random_state=SEED)
    X_tr, X_te, y_tr, y_te = X[itr], X[ite], y[itr], y[ite]
    src_te = source[ite]
    log(f"split train={len(y_tr):,} test={len(y_te):,}")

    # 2. scaler fitted on the training split only
    scaler = StandardScaler().fit(X_tr)
    X_tr_s, X_te_s = scaler.transform(X_tr), scaler.transform(X_te)

    # 3. SMOTE on the training split only
    attack_ratio = y_tr.mean()
    log(f"applying SMOTE (training attack ratio {attack_ratio:.4f})")
    X_res, y_res = SMOTE(random_state=SEED).fit_resample(X_tr_s, y_tr)
    log(f"resampled train {X_res.shape} balance={np.bincount(y_res)}")

    models, metrics, cv_results = {}, {}, {}

    # ---- supervised models ----
    specs = {
        "random_forest": RandomForestClassifier(
            n_estimators=100, random_state=SEED, n_jobs=-1
        ),
        "xgboost": XGBClassifier(
            n_estimators=100, max_depth=6, random_state=SEED,
            n_jobs=-1, eval_metric="logloss", tree_method="hist",
        ),
    }

    for name, clf in specs.items():
        log(f"training {name}")
        t0 = time.time()
        clf.fit(X_res, y_res)
        log(f"  fitted in {time.time() - t0:.1f}s")
        pred = clf.predict(X_te_s)
        proba = clf.predict_proba(X_te_s)[:, 1]
        metrics[name] = binary_metrics(y_te, pred, proba)
        log(f"  test  {fmt(metrics[name])}")
        models[name] = clf

    # ---- unsupervised model, fitted on benign training rows only ----
    log("training isolation_forest (benign rows only)")
    benign = X_tr_s[y_tr == 0]
    iso = IsolationForest(
        n_estimators=100,
        contamination=float(np.clip(attack_ratio, 1e-4, 0.5)),
        random_state=SEED,
        n_jobs=-1,
    ).fit(benign)
    iso_pred = (iso.predict(X_te_s) == -1).astype(int)
    iso_score = -iso.score_samples(X_te_s)  # higher = more anomalous
    metrics["isolation_forest"] = binary_metrics(y_te, iso_pred, iso_score)
    log(f"  test  {fmt(metrics['isolation_forest'])}")
    models["isolation_forest"] = iso

    # ---- cross-validation, SMOTE inside each fold ----
    if not args.no_cv:
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
        for name, clf in specs.items():
            log(f"5-fold CV {name} (SMOTE inside folds)")
            t0 = time.time()
            pipe = ImbPipeline([
                ("scaler", StandardScaler()),
                ("smote", SMOTE(random_state=SEED)),
                ("clf", clf.__class__(**clf.get_params())),
            ])
            res = cross_validate(
                pipe, X_tr, y_tr, cv=skf,
                scoring=["accuracy", "precision", "recall", "f1", "roc_auc"],
                n_jobs=1,
            )
            cv_results[name] = {
                k.replace("test_", ""): (float(np.mean(v)), float(np.std(v)))
                for k, v in res.items() if k.startswith("test_")
            }
            log(f"  done in {time.time() - t0:.1f}s  " + "  ".join(
                f"{k}={m:.4f}+/-{s:.4f}" for k, (m, s) in cv_results[name].items()))

    # ---- per-source breakdown on the test split ----
    # The corpus is assembled from sources with structurally different feature
    # coverage: flow rows carry no payload features and payload rows carry no
    # flow features. Aggregate metrics can therefore be satisfied by learning
    # which source a row came from. Reporting per source exposes that.
    per_source = {}
    best = models["xgboost"]
    pred_all = best.predict(X_te_s)
    for s in sorted(set(src_te)):
        mask = src_te == s
        if mask.sum() == 0:
            continue
        per_source[s] = binary_metrics(y_te[mask], pred_all[mask])
        per_source[s]["n"] = int(mask.sum())
        per_source[s]["attacks"] = int(y_te[mask].sum())

    log("per-source (XGBoost) on test split:")
    for s, m in per_source.items():
        log(f"  {s:<22} n={m['n']:>7,} attacks={m['attacks']:>6,}  {fmt(m)}")

    # ---- feature importances ----
    importances = {
        "random_forest": dict(zip(
            CANONICAL_FEATURE_ORDER,
            models["random_forest"].feature_importances_.astype(float))),
        "xgboost": dict(zip(
            CANONICAL_FEATURE_ORDER,
            models["xgboost"].feature_importances_.astype(float))),
    }

    # ---- persist ----
    for name, model in models.items():
        joblib.dump(model, MODEL_DIR / f"{name}.pkl")
    joblib.dump(scaler, MODEL_DIR / "scaler.pkl")
    (MODEL_DIR / "feature_order.json").write_text(
        json.dumps({"feature_order": CANONICAL_FEATURE_ORDER}, indent=2), encoding="utf-8")

    summary = {
        "corpus_shape": list(df.shape),
        "class_balance": {"benign": int(counts[0]), "attack": int(counts[1])},
        "split": {"train": int(len(y_tr)), "test": int(len(y_te))},
        "resampled_train": int(len(y_res)),
        "metrics": metrics,
        "cv": cv_results,
        "per_source": per_source,
        "importances": importances,
    }
    (MODEL_DIR / "training_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    log(f"saved models, scaler, feature_order.json and training_summary.json to {MODEL_DIR}")
    return summary


if __name__ == "__main__":
    main()
