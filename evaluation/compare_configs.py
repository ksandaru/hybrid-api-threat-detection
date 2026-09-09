"""
Phase 9 - comparative evaluation of detection configurations on live traffic.

Compares four configurations on the recorded traffic from Phase 8:

    none    no detection - the no-control baseline
    rules   signature engine only
    ml      payload classifier only
    hybrid  both, combined by noisy-OR (the proposed framework)

The comparison is **paired**: every configuration is scored on the byte-identical
set of requests, because the detection middleware records the rule score and the
ML score separately for each request it inspects. Deriving all four decisions
from one recorded run is methodologically stronger than running the stack four
times, since it removes run-to-run variation in the generated traffic and lets
the comparison use McNemar's test, which is the correct test for two classifiers
evaluated on the same samples.

Significance is reported with McNemar's exact test rather than a t-test across
repeated runs. The two answer different questions: a t-test asks whether mean
performance differs across runs, whereas McNemar asks whether the two detectors
disagree asymmetrically on the same requests - which is the question here, and it
does not require the runs to be repeated.

Run:
    ml/venv/Scripts/python.exe evaluation/compare_configs.py
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).parent.parent
TRAFFIC = ROOT / "evaluation" / "traffic"
TRAFFIC_MODSEC = ROOT / "evaluation" / "traffic_modsec"
FIG_DIR = ROOT / "evaluation" / "figures"
OUT_JSON = ROOT / "evaluation" / "phase9_configs.json"

# The deployed decision threshold on the combined score, and the ML service's
# own operating point (chosen on the validation split during training).
COMBINED_THRESHOLD = 0.70
ML_THRESHOLD = 0.77

CONFIGS = ["none", "rules", "ml", "hybrid"]

# ModSecurity v3 with the OWASP Core Rule Set, run as a reverse proxy in front
# of the same API with its own detection disabled, so the WAF is the only
# control. Recorded in a separate session because it is an external system and
# cannot be derived from the internal scores. The generators are seeded, so the
# request sequence is identical by construction and the two sessions pair by
# position within each generator - stated here because that assumption is what
# makes the McNemar comparison against it legitimate.
MODSEC = "modsec"


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load(directory=None):
    rows = []
    for p in sorted((directory or TRAFFIC).glob("*.csv")):
        with p.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("error"):
                    continue
                lab = r.get("expected_label")
                if lab not in ("0", "1"):
                    continue
                rows.append({
                    "y": int(lab),
                    "attack_type": r.get("attack_type") or "none",
                    "path": r.get("path") or "",
                    "generator": r.get("generator") or p.stem,
                    "rule": f(r.get("rule_score")),
                    "ml": f(r.get("ml_score")),
                    "combined": f(r.get("score")),
                    "alerts": r.get("alerts") or "",
                    "latency": f(r.get("latency_ms")),
                    "blocked": r.get("blocked") == "1",
                })
    return rows


def decide(row, config):
    """What each configuration would have decided about this request."""
    if config == "none":
        return 0
    if config == "rules":
        return int((row["rule"] or 0.0) >= COMBINED_THRESHOLD)
    if config == "ml":
        # The classifier is only consulted on payload-bearing endpoints, so
        # where it was never asked it has no opinion and cannot block.
        return 0 if row["ml"] is None else int(row["ml"] >= ML_THRESHOLD)
    if config == "hybrid":
        if row["combined"] is not None:
            return int(row["combined"] >= COMBINED_THRESHOLD)
        return int(row["blocked"])
    raise ValueError(config)


def align_modsec(rows, ms_rows):
    """
    Pair the external WAF session with the internal one by position within each
    generator. The generators are seeded, so the two sessions issue the same
    request sequence; this verifies that assumption by checking the labels agree
    at every position rather than trusting it.
    """
    by_gen = defaultdict(list)
    for r in ms_rows:
        by_gen[r["generator"]].append(r)
    cursor = defaultdict(int)
    out = []
    for r in rows:
        g = r["generator"]
        i = cursor[g]
        cursor[g] += 1
        if i >= len(by_gen.get(g, [])):
            return None, f"{g} shorter in the WAF session"
        m = by_gen[g][i]
        if m["y"] != r["y"]:
            return None, f"label mismatch in {g} at position {i}"
        out.append(int(m["blocked"]))
    return out, None


def metrics(y, pred):
    y, pred = np.asarray(y), np.asarray(pred)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "accuracy": (tp + tn) / max(len(y), 1),
        "precision": prec,
        "recall": rec,
        "f1": (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0,
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def bootstrap_ci(y, pred, stat="f1", n=2000, seed=42):
    """Percentile bootstrap CI - the traffic sample is small, so state the range."""
    rng = np.random.default_rng(seed)
    y, pred = np.asarray(y), np.asarray(pred)
    idx = np.arange(len(y))
    vals = []
    for _ in range(n):
        s = rng.choice(idx, size=len(idx), replace=True)
        vals.append(metrics(y[s], pred[s])[stat])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def mcnemar(y, a, b):
    """
    Exact McNemar test on the discordant pairs.

    b01 = requests config A got right and B got wrong; b10 = the reverse.
    Only discordant pairs carry information about which is better.
    """
    y, a, b = np.asarray(y), np.asarray(a), np.asarray(b)
    ca, cb = (a == y), (b == y)
    b01 = int((ca & ~cb).sum())
    b10 = int((~ca & cb).sum())
    n = b01 + b10
    if n == 0:
        return {"b01": 0, "b10": 0, "p_value": 1.0, "note": "no discordant pairs"}
    p = float(stats.binomtest(b01, n, 0.5).pvalue)
    return {"b01": b01, "b10": b10, "n_discordant": n, "p_value": p}


def pct(vals, q):
    return float(np.percentile(vals, q)) if len(vals) else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    rows = load()
    if not rows:
        raise SystemExit(f"no traffic CSVs in {TRAFFIC}")
    y = [r["y"] for r in rows]
    print(f"loaded {len(rows)} labelled requests "
          f"({sum(y)} attack / {len(y) - sum(y)} benign)\n")

    preds = {c: [decide(r, c) for r in rows] for c in CONFIGS}
    order = list(CONFIGS)

    # ---- external WAF baseline, if that session was recorded ------------
    ms_rows = load(TRAFFIC_MODSEC) if TRAFFIC_MODSEC.exists() else []
    if ms_rows:
        aligned, mismatch = align_modsec(rows, ms_rows)
        if aligned is None:
            print(f"NOTE: ModSecurity session does not align with the internal "
                  f"session ({mismatch}); excluded from the comparison.\n")
        else:
            preds[MODSEC] = aligned
            order.insert(3, MODSEC)
            print(f"ModSecurity baseline loaded: {len(ms_rows)} requests, "
                  f"aligned by position within each generator\n")

    results = {c: metrics(y, preds[c]) for c in order}
    for c in order:
        results[c]["f1_ci95"] = bootstrap_ci(y, preds[c], "f1")
        results[c]["fpr_ci95"] = bootstrap_ci(y, preds[c], "fpr")

    # ---- headline table -------------------------------------------------
    print("=" * 92)
    print("CONFIGURATION COMPARISON - identical traffic, paired")
    print("=" * 92)
    print(f"{'config':<10}{'acc':>8}{'prec':>8}{'recall':>9}{'F1':>8}"
          f"{'FPR':>8}{'  F1 95% CI':>20}{'  blocked':>11}")
    print("-" * 92)
    for c in order:
        m = results[c]
        lo, hi = m["f1_ci95"]
        print(f"{c:<10}{m['accuracy']:>8.4f}{m['precision']:>8.4f}{m['recall']:>9.4f}"
              f"{m['f1']:>8.4f}{m['fpr']:>8.4f}   [{lo:.3f}, {hi:.3f}]"
              f"{m['tp'] + m['fp']:>11}")

    # ---- significance ---------------------------------------------------
    print("\n" + "=" * 92)
    print("McNEMAR EXACT TEST - hybrid vs each baseline (same requests)")
    print("=" * 92)
    sig = {}
    for c in [x for x in order if x != "hybrid"]:
        t = mcnemar(y, preds[c], preds["hybrid"])
        sig[f"hybrid_vs_{c}"] = t
        if t.get("n_discordant"):
            verdict = ("hybrid better" if t["b10"] > t["b01"] else
                       "baseline better" if t["b01"] > t["b10"] else "tied")
            star = "significant" if t["p_value"] < 0.05 else "not significant"
            print(f"  hybrid vs {c:<7} baseline-only-correct={t['b01']:>4}  "
                  f"hybrid-only-correct={t['b10']:>4}  p={t['p_value']:.3e}  "
                  f"({verdict}, {star})")
        else:
            print(f"  hybrid vs {c:<7} {t['note']}")

    # ---- per attack type ------------------------------------------------
    print("\n" + "=" * 92)
    print("DETECTION RATE BY ATTACK TYPE")
    print("=" * 92)
    fam = defaultdict(list)
    for i, r in enumerate(rows):
        if r["y"] == 1:
            fam[r["attack_type"]].append(i)
    detail = [c for c in order if c != "none"]
    hdr = "".join(f"{c:>10}" for c in detail)
    print(f"{'attack type':<26}{'n':>6}{hdr}")
    print("-" * 92)
    per_type = {}
    for t in sorted(fam):
        ix = fam[t]
        row = {c: sum(preds[c][i] for i in ix) / len(ix) for c in detail}
        per_type[t] = {**row, "n": len(ix)}
        print(f"{t:<26}{len(ix):>6}" + "".join(f"{row[c]:>10.1%}" for c in detail))

    # ---- latency --------------------------------------------------------
    all_lat = [r["latency"] for r in rows if r["latency"] is not None]
    short = [r["latency"] for r in rows
             if r["latency"] is not None and r["ml"] is None and r["alerts"]]
    withml = [r["latency"] for r in rows if r["latency"] is not None and r["ml"] is not None]
    lat = {
        "hybrid_all": {"n": len(all_lat), "p50": pct(all_lat, 50),
                       "p95": pct(all_lat, 95), "p99": pct(all_lat, 99)},
        "ml_consulted": {"n": len(withml), "p50": pct(withml, 50),
                         "p95": pct(withml, 95), "p99": pct(withml, 99)},
        "rule_short_circuit": {"n": len(short), "p50": pct(short, 50),
                               "p95": pct(short, 95), "p99": pct(short, 99)},
    }
    print("\n" + "=" * 92)
    print("LATENCY (ms) - measured on the same traffic")
    print("=" * 92)
    print(f"{'path':<24}{'n':>7}{'p50':>10}{'p95':>10}{'p99':>10}")
    print("-" * 92)
    for k, v in lat.items():
        print(f"{k:<24}{v['n']:>7}{v['p50']:>10.2f}{v['p95']:>10.2f}{v['p99']:>10.2f}")
    if withml and short:
        u = stats.mannwhitneyu(withml, short, alternative="greater")
        print(f"\n  Mann-Whitney U, ML-consulted vs short-circuit: p={u.pvalue:.3e}")
        lat["short_circuit_test"] = {"p_value": float(u.pvalue)}

    store = {"n_requests": len(rows), "n_attack": int(sum(y)),
             "thresholds": {"combined": COMBINED_THRESHOLD, "ml": ML_THRESHOLD},
             "config_order": order,
             "configs": results, "significance": sig,
             "per_attack_type": per_type, "latency": lat}
    OUT_JSON.write_text(json.dumps(store, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT_JSON}")

    if not args.no_figures:
        make_figure(results, per_type, lat, order)


def make_figure(results, per_type, lat, order):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
    COL = {"none": "#808080", "rules": "#1F4E79", "ml": "#C55A11",
           "modsec": "#7030A0", "hybrid": "#375623"}

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    keys = ["precision", "recall", "f1", "fpr"]
    x = np.arange(len(keys))
    n = len(order); w = 0.8 / n
    for i, c in enumerate(order):
        vals = [results[c][k] for k in keys]
        bars = axes[0].bar(x + (i - (n - 1) / 2) * w, vals, w, label=c, color=COL.get(c, "#444"))
        for b in bars:
            if b.get_height() > 0.01:
                axes[0].text(b.get_x() + b.get_width() / 2, b.get_height() + 0.02,
                             f"{b.get_height():.2f}", ha="center", fontsize=6)
    axes[0].set_xticks(x, ["Precision", "Recall", "F1", "FPR"])
    axes[0].set_ylim(0, 1.15)
    axes[0].set_ylabel("Score")
    axes[0].legend(frameon=False, fontsize=7.5, ncol=n, loc="upper center")
    axes[0].grid(axis="y", alpha=0.25, linewidth=0.5)
    axes[0].set_title("Detection performance by configuration", fontsize=10)

    detail = [c for c in order if c != "none"]
    types = sorted(per_type)
    x2 = np.arange(len(types)); m = len(detail); w2 = 0.8 / m
    for i, c in enumerate(detail):
        vals = [per_type[t].get(c, 0.0) for t in types]
        axes[1].bar(x2 + (i - (m - 1) / 2) * w2, vals, w2, label=c, color=COL.get(c, "#444"))
    axes[1].set_xticks(x2, [t.replace("sqli_", "") for t in types],
                       rotation=30, ha="right", fontsize=7.5)
    axes[1].set_ylim(0, 1.15)
    axes[1].set_ylabel("Detection rate")
    axes[1].legend(frameon=False, fontsize=7.5, ncol=m, loc="upper center")
    axes[1].grid(axis="y", alpha=0.25, linewidth=0.5)
    axes[1].set_title("Detection rate by attack type", fontsize=10)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "config_comparison.png", bbox_inches="tight")
    plt.close(fig)
    print(f"figure written to {FIG_DIR / 'config_comparison.png'}")


if __name__ == "__main__":
    main()
