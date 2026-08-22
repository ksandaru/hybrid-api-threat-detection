"""
Re-select the detection threshold on representative traffic.

This closes the blocker recorded at Phase 6: the hybrid pipeline had a 33% false
positive rate on live-shaped benign traffic against 0% for rules alone, because
the decision threshold (0.77 on the ML score, 0.7 on the combined score) was
chosen on corpus validation rows that do not resemble this API's traffic. The
right threshold cannot be known until there is representative traffic to choose
it on -- which the Phase 8 generators now produce, each request carrying the
combined score the pipeline gave it (via the trace headers).

What this does:
  1. read every generated CSV under evaluation/traffic/
  2. for a grid of candidate combined-decision thresholds, compute benign false
     positive rate and per-attack-type recall, treating rule-blocked requests as
     detected regardless of threshold (a high-severity rule short-circuits ahead
     of the score)
  3. report the operating point at the current threshold, and recommend one that
     holds benign FPR under a target while keeping attack recall as high as
     possible
  4. write the curve and the recommendation to evaluation/threshold_recalibration.md

It changes nothing on its own. Moving the boundary is a one-line change to
DETECTION_THRESHOLD, made deliberately after reading the recommendation, not a
side effect of running this.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

TRAFFIC = Path(__file__).resolve().parent.parent / "evaluation" / "traffic"
REPORT = Path(__file__).resolve().parent.parent / "evaluation" / "threshold_recalibration.md"
CURRENT_THRESHOLD = 0.7
_REPORT_ROWS = []  # set in main(), read by write_report for the endpoint breakdown


def _endpoint(path):
    """Collapse /api/orders/417 -> /api/orders so ids do not fragment the table."""
    parts = [p for p in path.split("?")[0].split("/") if p]
    return "/" + "/".join(parts[:2]) if len(parts) >= 2 else path


def load_rows():
    rows = []
    for csv_path in sorted(TRAFFIC.glob("*.csv")):
        with csv_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("error"):
                    continue
                rows.append(row)
    return rows


def _score(row):
    try:
        return float(row["score"]) if row["score"] != "" else None
    except (KeyError, ValueError):
        return None


def _rule_blocked(row):
    # A request the rules blocked outright is detected at any threshold: the
    # high-severity short-circuit fires before the combined score is consulted.
    return row.get("alerts", "") != "" and row["blocked"] == "1"


def evaluate(rows, threshold):
    """Detected if a rule blocked it, or its combined score meets threshold."""
    benign_total = benign_fp = 0
    attack_total = attack_hit = 0
    per_type = defaultdict(lambda: [0, 0])  # type -> [hit, total]

    for row in rows:
        label = row["expected_label"]
        score = _score(row)
        detected = _rule_blocked(row) or (score is not None and score >= threshold)
        if label == "0":
            benign_total += 1
            benign_fp += int(detected)
        elif label == "1":
            attack_total += 1
            attack_hit += int(detected)
            t = row["attack_type"]
            per_type[t][1] += 1
            per_type[t][0] += int(detected)

    return {
        "threshold": threshold,
        "benign_total": benign_total,
        "benign_fpr": benign_fp / benign_total if benign_total else 0.0,
        "attack_total": attack_total,
        "attack_recall": attack_hit / attack_total if attack_total else 0.0,
        "per_type": {k: (h / t if t else 0.0, h, t) for k, (h, t) in per_type.items()},
    }


def sweep(rows, lo=0.30, hi=0.95, step=0.01):
    grid = [round(lo + i * step, 2) for i in range(int((hi - lo) / step) + 1)]
    return [evaluate(rows, t) for t in grid]


def recommend(curve, target_fpr):
    """Lowest-FPR-tie-broken-by-recall point that stays under the target FPR."""
    feasible = [c for c in curve if c["benign_fpr"] <= target_fpr]
    if not feasible:
        return None
    # among those under the FPR cap, take the highest attack recall, then the
    # lowest threshold that achieves it (least aggressive that still works)
    best_recall = max(c["attack_recall"] for c in feasible)
    winners = [c for c in feasible if c["attack_recall"] == best_recall]
    return min(winners, key=lambda c: c["threshold"])


def fmt_pct(x):
    return f"{x * 100:.1f}%"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target-fpr", type=float, default=0.02,
                    help="maximum acceptable benign false positive rate")
    args = ap.parse_args()

    rows = load_rows()
    if not rows:
        raise SystemExit(f"no traffic CSVs in {TRAFFIC}. Run the generators first.")
    _REPORT_ROWS[:] = rows

    scored = sum(1 for r in rows if _score(r) is not None)
    print(f"loaded {len(rows)} requests ({scored} with a combined score)")
    if scored < len(rows):
        print("  note: rows without a score were served with DETECTION_TRACE off;")
        print("        re-run the generators against a stack started with "
              "DETECTION_TRACE=1 for a full curve.")

    curve = sweep(rows)
    current = evaluate(rows, CURRENT_THRESHOLD)
    rec = recommend(curve, args.target_fpr)

    print(f"\ncurrent threshold {CURRENT_THRESHOLD}:")
    print(f"  benign FPR {fmt_pct(current['benign_fpr'])}"
          f"  attack recall {fmt_pct(current['attack_recall'])}")
    if rec:
        print(f"\nrecommended threshold {rec['threshold']} "
              f"(target FPR <= {fmt_pct(args.target_fpr)}):")
        print(f"  benign FPR {fmt_pct(rec['benign_fpr'])}"
              f"  attack recall {fmt_pct(rec['attack_recall'])}")
    else:
        print(f"\nno threshold holds benign FPR <= {fmt_pct(args.target_fpr)}; "
              "the rule stage alone determines the floor")

    write_report(curve, current, rec, args.target_fpr, len(rows), scored)
    print(f"\nwrote {REPORT}")


def write_report(curve, current, rec, target_fpr, n, scored):
    lines = []
    lines.append("# Threshold recalibration on representative traffic\n")
    lines.append("Generated by `attack-sim/recalibrate_threshold.py` from the "
                 "CSVs in `evaluation/traffic/`.\n")
    lines.append(f"- Requests analysed: **{n}** ({scored} carrying a combined score)")
    lines.append(f"- Current combined-decision threshold: **{CURRENT_THRESHOLD}**")
    lines.append(f"- Target benign false positive rate: **{fmt_pct(target_fpr)}**\n")

    lines.append("## Operating point at the current threshold\n")
    lines.append(f"Benign FPR **{fmt_pct(current['benign_fpr'])}**, "
                 f"attack recall **{fmt_pct(current['attack_recall'])}** "
                 f"over {current['attack_total']} attack and "
                 f"{current['benign_total']} benign requests.\n")

    if rec:
        lines.append("## Recommendation\n")
        lines.append(f"Move the threshold to **{rec['threshold']}**: benign FPR "
                     f"**{fmt_pct(rec['benign_fpr'])}**, attack recall "
                     f"**{fmt_pct(rec['attack_recall'])}**. Set "
                     f"`DETECTION_THRESHOLD={rec['threshold']}`.\n")

    lines.append("## Detection rate by attack type (at the recommended threshold)\n")
    point = rec or current
    lines.append("| Attack type | Recall | Detected / total |")
    lines.append("|---|---:|---:|")
    for t in sorted(point["per_type"]):
        recall, hit, total = point["per_type"][t]
        lines.append(f"| {t} | {fmt_pct(recall)} | {hit}/{total} |")
    lines.append("")

    lines.append("## Where the benign false positives fall\n")
    lines.append("A single blended false positive rate hides the actual "
                 "pattern. Broken down by endpoint, at a threshold of 0.80:\n")
    lines.append("| Endpoint | Benign requests | Scoring ≥ 0.80 |")
    lines.append("|---|---:|---:|")
    by_ep_total, by_ep_high = defaultdict(int), defaultdict(int)
    for row in _REPORT_ROWS:
        if row["expected_label"] != "0":
            continue
        ep = _endpoint(row["path"])
        by_ep_total[ep] += 1
        s = _score(row)
        if s is not None and s >= 0.80:
            by_ep_high[ep] += 1
    for ep in sorted(by_ep_total):
        lines.append(f"| {ep} | {by_ep_total[ep]} | {by_ep_high[ep]} |")
    lines.append("")
    lines.append("If the false positives concentrate on `/api/auth/*`, the "
                 "cause is not the threshold: it is the payload classifier "
                 "scoring credential POST bodies, whose high entropy and "
                 "special-character density resemble the attack payloads it was "
                 "trained on. The behavioural attacks against those endpoints "
                 "(brute force, credential stuffing) are detected by the rule "
                 "stage, not the payload model, so the model has nothing to add "
                 "there and a great deal to get wrong.\n")

    lines.append("## Threshold curve\n")
    lines.append("| Threshold | Benign FPR | Attack recall |")
    lines.append("|---:|---:|---:|")
    for c in curve:
        if round(c["threshold"] * 100) % 5 == 0:  # every 0.05, to keep it short
            lines.append(f"| {c['threshold']:.2f} | {fmt_pct(c['benign_fpr'])} "
                         f"| {fmt_pct(c['attack_recall'])} |")
    lines.append("")

    REPORT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
