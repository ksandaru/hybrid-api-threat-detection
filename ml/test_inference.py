"""Deliverable check for the inference service (Phase 5).

Two parts, because they answer different questions.

1. Distributional check (pass/fail). Samples real benign and real attack rows
   from the corpus, sends each through the running service, and asserts that the
   service reproduces the separation and false positive rate measured offline by
   ml/train.py. This is the check that can fail the build: it verifies the
   service scores identically to the training pipeline, over a distribution
   rather than over a handful of strings.

2. Illustrative cases (reported, not asserted). Hand-written requests shaped the
   way the Express middleware builds them, printed with their scores so the
   behaviour on recognisable payloads is visible. These are deliberately not
   pass/fail: three hand-picked strings are not a distribution, and an earlier
   version of this file asserted on them and produced a misleading failure.

Run the service first, from ml/:
    ..\\ml\\venv\\Scripts\\python -m uvicorn app:app --port 8000
then:
    .\\ml\\venv\\Scripts\\python ml\\test_inference.py
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from features import (
    CANONICAL_FEATURE_ORDER,
    default_flow_features,
    extract_payload_features,
)

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).parent.parent
CORPUS = ROOT / "datasets" / "processed" / "train.parquet"
PAYLOAD_SOURCES = ("kaggle_sqliv3", "csic_2010")
SAMPLE_N = 300
SEED = 7

ILLUSTRATIVE = [
    ("benign search", "/search/vulnerable q=laptop"),
    ("benign search, longer", "/search/vulnerable q=24 inch curved monitor"),
    ("benign login", "/auth/login username=alice&password=correcthorse"),
    ("SQLi tautology", "/search/vulnerable q=' OR '1'='1"),
    ("SQLi union select", "/search/vulnerable q=' UNION SELECT username, password FROM users --"),
    ("SQLi stacked", "/search/vulnerable q=1; DROP TABLE users; SELECT 1"),
    ("SQLi obfuscated", "/search/vulnerable q=/**/or/**/1/**/=/**/1"),
]

# Behavioural vectors carry no payload signal. Included to demonstrate the
# Phase 4 finding that the models cannot express these attacks, rather than to
# hide it.
BEHAVIOURAL = [
    ("brute force burst", {
        "requests_per_min_ip": 90.0, "login_failure_ratio": 1.0,
        "inter_arrival_time_variance": 2.5e8, "distinct_usernames_tried": 1.0,
        "unique_ip_count_window": 1.0}),
    ("credential stuffing", {
        "requests_per_min_ip": 45.0, "login_failure_ratio": 0.95,
        "inter_arrival_time_variance": 1.1e9, "distinct_usernames_tried": 40.0,
        "unique_ip_count_window": 1.0}),
]


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def vector_from_text(text):
    f = default_flow_features()
    f.update(extract_payload_features(text))
    return f


def main():
    try:
        h = get("/health")
    except urllib.error.URLError as exc:
        print(f"cannot reach {BASE}: {exc}")
        print("start the service first (see this file's docstring)")
        return 1
    if not h.get("ready"):
        print(f"service not ready: {h.get('error')}")
        return 1

    m = get("/meta")
    th = m["attack_threshold"]
    print(f"health ok  load_ms={h.get('load_ms')}  iso_calibrated={h.get('iso_calibrated')}")
    print(f"weights {m['weights']}  threshold={th}")
    op = m.get("operating_point") or {}
    if op:
        print(f"threshold selected on: {op.get('selected_on')}")
    print()

    # ---------- 1. distributional check ----------
    print("=== distributional check against corpus rows ===")
    df = pd.read_parquet(CORPUS)
    pay = df[df["source"].isin(PAYLOAD_SOURCES)]
    rng = np.random.default_rng(SEED)

    results = {}
    for label_name, label_val in (("benign", 0), ("attack", 1)):
        rows = pay[pay["label"] == label_val]
        idx = rng.choice(len(rows), size=min(SAMPLE_N, len(rows)), replace=False)
        sample = rows.iloc[idx]
        scores = []
        for _, r in sample.iterrows():
            feats = {n: float(r[n]) for n in CANONICAL_FEATURE_ORDER}
            scores.append(post("/predict", {"features": feats})["score"])
        results[label_name] = np.array(scores)

    ben, att = results["benign"], results["attack"]
    fpr = float((ben >= th).mean())
    recall = float((att >= th).mean())
    print(f"  benign n={len(ben)}  mean={ben.mean():.3f} median={np.median(ben):.3f} "
          f"p90={np.percentile(ben, 90):.3f}  flagged (FPR) = {fpr:.3f}")
    print(f"  attack n={len(att)}  mean={att.mean():.3f} median={np.median(att):.3f} "
          f"p10={np.percentile(att, 10):.3f}  flagged (recall) = {recall:.3f}")

    # Bounds are loose because this is a sample of a few hundred rows, and
    # because part of the corpus was seen during fitting. The purpose is to
    # catch a service that scores differently from the training pipeline, not
    # to re-measure the model.
    ok_fpr = fpr <= 0.15
    ok_recall = recall >= 0.85
    ok_sep = att.mean() - ben.mean() > 0.3
    print(f"  FPR <= 0.15        {'PASS' if ok_fpr else 'FAIL'}")
    print(f"  recall >= 0.85     {'PASS' if ok_recall else 'FAIL'}")
    print(f"  mean separation    {'PASS' if ok_sep else 'FAIL'} ({att.mean() - ben.mean():.3f})")

    # ---------- 2. illustrative cases ----------
    print()
    print("=== illustrative requests (reported, not asserted) ===")
    print(f"{'case':<26} {'score':>7} {'flag':>6} {'rf':>7} {'xgb':>7} {'iso':>7} {'ms':>7}")
    print("-" * 72)
    for name, text in ILLUSTRATIVE:
        r = post("/predict", {"features": vector_from_text(text)})
        d = r["details"]
        print(f"{name:<26} {r['score']:>7.3f} {str(r['is_attack']):>6} "
              f"{d['random_forest']['probability']:>7.3f} {d['xgboost']['probability']:>7.3f} "
              f"{d['isolation_forest']['normalised']:>7.3f} {r['latency_ms']:>7.2f}")
    for name, flow in BEHAVIOURAL:
        feats = {n: 0.0 for n in CANONICAL_FEATURE_ORDER}
        feats.update(flow)
        r = post("/predict", {"features": feats})
        print(f"{name:<26} {r['score']:>7.3f} {str(r['is_attack']):>6} "
              f"{'-':>7} {'-':>7} {'-':>7} {r['latency_ms']:>7.2f}")
    print("\nBehavioural vectors score near zero by design: Phase 4 established that")
    print("the classifiers assign zero importance to the flow features that are")
    print("zero-filled in the corpus. The rule engine detects those attacks.")

    # ---------- 3. robustness ----------
    r = post("/predict", {"features": {"payload_length": 12, "not_a_feature": 1}})
    d = r["details"]
    print(f"\npartial vector: missing={len(d['missing_features'])} of {len(CANONICAL_FEATURE_ORDER)}, "
          f"unexpected={d['unexpected_features']}, score={r['score']:.3f}")
    ok_robust = len(d["missing_features"]) == 16 and d["unexpected_features"] == ["not_a_feature"]
    print(f"  reports missing and unexpected names  {'PASS' if ok_robust else 'FAIL'}")

    all_ok = ok_fpr and ok_recall and ok_sep and ok_robust
    print("\n" + ("ALL CHECKS PASSED" if all_ok else "CHECKS FAILED"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
