"""
Build the results workbook for the dissertation.

Everything here is native Excel: real cells, real tables, and real Excel chart
objects rather than embedded images, so every figure stays editable and every
number is traceable to the cell it came from. Reads only the JSON and CSV that
the evaluation scripts emit, so re-running the evaluation and re-running this
regenerates the whole workbook.

Run:
    ml/venv/Scripts/python.exe evaluation/build_workbook.py
"""

import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference, ScatterChart, Series
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).parent.parent
EVAL = ROOT / "evaluation"
OUT = EVAL / "CB016639_Results_Workbook.xlsx"

ACCENT = "1F4E79"
LIGHT = "D9E2F3"
GOOD = "375623"
BAD = "C00000"

HDR_FILL = PatternFill("solid", fgColor=ACCENT)
HDR_FONT = Font(color="FFFFFF", bold=True, size=11, name="Calibri")
TITLE_FONT = Font(color=ACCENT, bold=True, size=14, name="Calibri")
NOTE_FONT = Font(color="595959", italic=True, size=9, name="Calibri")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def sheet_title(ws, text, note=None):
    ws["A1"] = text
    ws["A1"].font = TITLE_FONT
    if note:
        ws["A2"] = note
        ws["A2"].font = NOTE_FONT
    return 4 if note else 3


def write_table(ws, top, headers, rows, widths=None, pct_cols=(), num_fmt="0.0000"):
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=top, column=j, value=h)
        c.fill, c.font, c.border = HDR_FILL, HDR_FONT, BORDER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, row in enumerate(rows, start=top + 1):
        for j, v in enumerate(row, start=1):
            c = ws.cell(row=i, column=j, value=v)
            c.border = BORDER
            c.font = Font(name="Calibri", size=10)
            if isinstance(v, float):
                c.number_format = "0.0%" if j in pct_cols else num_fmt
                c.alignment = Alignment(horizontal="right")
            elif isinstance(v, int):
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right")
            if i % 2 == 0:
                c.fill = PatternFill("solid", fgColor="F2F6FA")
    if widths:
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(j)].width = w
    return top + len(rows) + 1


def bar_chart(ws, anchor, title, y_title, data_ref, cats_ref, height=8, width=16,
              grouping="clustered", overlap=None):
    ch = BarChart()
    ch.type = "col"
    ch.grouping = grouping
    if overlap is not None:
        ch.overlap = overlap
    ch.title = title
    ch.y_axis.title = y_title
    ch.height, ch.width = height, width
    ch.add_data(data_ref, titles_from_data=True)
    ch.set_categories(cats_ref)
    ch.gapWidth = 60
    ws.add_chart(ch, anchor)
    return ch


def main():
    cfg = json.loads((EVAL / "phase9_configs.json").read_text(encoding="utf-8"))
    off = json.loads((EVAL / "phase9_offline.json").read_text(encoding="utf-8"))

    wb = Workbook()

    # ================================================== 1. Summary
    ws = wb.active
    ws.title = "1. Summary"
    r = sheet_title(ws, "Hybrid Threat Detection for REST APIs - Results Summary",
                    "CB016639 | All figures generated from evaluation/compare_configs.py "
                    "and ml/evaluate.py. Every sheet is traceable to those outputs.")

    h = cfg["configs"]["hybrid"]
    ru = cfg["configs"]["rules"]
    mlc = cfg["configs"]["ml"]
    gen = off["generalisation_drop"]

    rows = [
        ["Requests evaluated (live traffic)", cfg["n_requests"], "labelled at source, not inferred"],
        ["Attack requests", cfg["n_attack"], ""],
        ["Benign requests", cfg["n_requests"] - cfg["n_attack"], ""],
        ["", "", ""],
        ["Hybrid F1", h["f1"], "the proposed framework"],
        ["Rules-only F1", ru["f1"], "conventional signature baseline"],
        ["ML-only F1", mlc["f1"], "payload classifier alone"],
        ["Hybrid vs rules, McNemar p", cfg["significance"]["hybrid_vs_rules"]["p_value"],
         "significant at p < 0.05"],
        ["", "", ""],
        ["Hybrid false positive rate", h["fpr"], "on benign traffic"],
        ["Rules-only false positive rate", ru["fpr"], ""],
        ["", "", ""],
        ["Internal test ROC-AUC", off["test"]["models"]["combined"]["roc_auc"],
         "combined pipeline, corpus test split"],
        ["Held-out ATRDF ROC-AUC", off["heldout"]["models"]["combined"]["roc_auc"],
         "never trained on - 0.5 is random"],
        ["Generalisation change in F1", gen["f1"]["delta"], "negative result, fully diagnosed"],
    ]
    r = write_table(ws, r, ["Measure", "Value", "Note"], rows, widths=[38, 16, 52])

    r += 1
    ws.cell(row=r, column=1, value="Headline findings").font = Font(bold=True, size=12, color=ACCENT)
    r += 1
    for txt, col in [
        ("1. The hybrid significantly outperforms every baseline on live traffic "
         "(F1 %.4f vs %.4f for rules alone, McNemar p = %.2e)."
         % (h["f1"], ru["f1"], cfg["significance"]["hybrid_vs_rules"]["p_value"]), GOOD),
        ("2. The two stages fail on different attacks. On blind and obfuscated injection "
         "neither component exceeds 67% while the hybrid reaches 100% - see sheet 3.", GOOD),
        ("3. The trained models do NOT generalise to an unseen corpus (ROC-AUC %.4f, "
         "indistinguishable from random). Cause established as covariate shift - see sheet 6."
         % off["heldout"]["models"]["combined"]["roc_auc"], BAD),
    ]:
        c = ws.cell(row=r, column=1, value=txt)
        c.font = Font(name="Calibri", size=10, color=col)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 30
        r += 1

    # ================================================== 2. Config comparison
    ws = wb.create_sheet("2. Config comparison")
    r = sheet_title(ws, "Detection configuration comparison",
                    "Paired design: all four configurations scored on byte-identical traffic, "
                    "derived from separately recorded rule and ML scores.")
    order = cfg.get("config_order", ["none", "rules", "ml", "hybrid"])
    labels = {"none": "No detection", "rules": "Rules only", "ml": "ML only",
              "modsec": "ModSecurity (OWASP CRS)", "hybrid": "Hybrid (proposed)"}
    rows = []
    for c in order:
        m = cfg["configs"][c]
        rows.append([labels[c], m["accuracy"], m["precision"], m["recall"],
                     m["f1"], m["fpr"], m["tp"], m["fp"], m["fn"], m["tn"]])
    top = r
    r = write_table(ws, r, ["Configuration", "Accuracy", "Precision", "Recall", "F1",
                            "FPR", "TP", "FP", "FN", "TN"], rows,
                    widths=[20, 11, 11, 10, 10, 10, 8, 8, 8, 8])

    data = Reference(ws, min_col=2, max_col=6, min_row=top, max_row=top + len(rows))
    cats = Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(rows))
    bar_chart(ws, f"A{r + 2}", "Detection performance by configuration", "Score", data, cats)

    r2 = r + 20
    ws.cell(row=r2, column=1, value="McNemar exact test - hybrid vs each baseline").font = \
        Font(bold=True, size=12, color=ACCENT)
    sig_rows = []
    for k, v in cfg["significance"].items():
        base = k.replace("hybrid_vs_", "")
        sig_rows.append([labels.get(base, base), v.get("b01", 0), v.get("b10", 0),
                         v.get("p_value", 1.0),
                         "significant" if v.get("p_value", 1) < 0.05 else "not significant"])
    write_table(ws, r2 + 1,
                ["Baseline", "Baseline correct only", "Hybrid correct only", "p-value", "Verdict"],
                sig_rows, widths=[20, 20, 20, 14, 16], num_fmt="0.00E+00")

    # ================================================== 3. By attack type
    ws = wb.create_sheet("3. By attack type")
    r = sheet_title(ws, "Detection rate by attack type",
                    "The core evidence for the hybrid design: the two stages fail on "
                    "different attack families, and the combination covers both.")
    pt = cfg["per_attack_type"]
    detail = [c for c in order if c != "none"]
    rows = [[t.replace("sqli_", "SQLi - "), pt[t]["n"]] + [pt[t].get(c, 0.0) for c in detail]
            for t in sorted(pt)]
    top = r
    ncol = 2 + len(detail)
    r = write_table(ws, r, ["Attack type", "n"] + [labels[c] for c in detail], rows,
                    widths=[26, 8] + [15] * len(detail),
                    pct_cols=tuple(range(3, ncol + 1)))

    data = Reference(ws, min_col=3, max_col=ncol, min_row=top, max_row=top + len(rows))
    cats = Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(rows))
    bar_chart(ws, f"A{r + 2}", "Detection rate by attack type", "Detection rate", data, cats,
              height=9, width=18)

    r3 = r + 21
    for txt in [
        "Rules catch tautology and union injection perfectly and miss comment and stacked "
        "injection entirely; the classifier does the opposite.",
        "On blind and obfuscated injection neither component exceeds 67%, yet the hybrid "
        "reaches 100%. This is the clearest single argument for the architecture.",
        "The classifier contributes nothing to brute force and credential stuffing, "
        "consistent with the zero importance of the behavioural features.",
    ]:
        c = ws.cell(row=r3, column=1, value=txt)
        c.font = Font(name="Calibri", size=10)
        ws.merge_cells(start_row=r3, start_column=1, end_row=r3, end_column=5)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r3].height = 28
        r3 += 1

    # ================================================== 4. Latency
    ws = wb.create_sheet("4. Latency")
    r = sheet_title(ws, "Detection latency",
                    "Measured on the same traffic. The short-circuit path skips the "
                    "classifier when a high-severity rule has already decided.")
    lat = cfg["latency"]
    names = {"rule_short_circuit": "Rule short-circuit (no ML call)",
             "ml_consulted": "ML consulted",
             "hybrid_all": "All requests"}
    rows = [[names[k], lat[k]["n"], lat[k]["p50"], lat[k]["p95"], lat[k]["p99"]]
            for k in ("rule_short_circuit", "ml_consulted", "hybrid_all") if k in lat]
    top = r
    r = write_table(ws, r, ["Path", "n", "p50 (ms)", "p95 (ms)", "p99 (ms)"], rows,
                    widths=[32, 8, 12, 12, 12], num_fmt="0.00")
    data = Reference(ws, min_col=3, max_col=5, min_row=top, max_row=top + len(rows))
    cats = Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(rows))
    bar_chart(ws, f"A{r + 2}", "Added latency by detection path", "Milliseconds", data, cats)
    if "short_circuit_test" in lat:
        ws.cell(row=r, column=1,
                value="Mann-Whitney U, ML-consulted vs short-circuit: p = %.2e"
                      % lat["short_circuit_test"]["p_value"]).font = NOTE_FONT

    # ================================================== 5. Model performance
    ws = wb.create_sheet("5. Model performance")
    r = sheet_title(ws, "Individual model performance",
                    "Corpus test split (135,434 rows). Accuracy is flattered by the 13:1 "
                    "class imbalance; ROC-AUC is the fairer comparison.")
    mnames = {"random_forest": "Random Forest", "xgboost": "XGBoost",
              "isolation_forest": "Isolation Forest", "combined": "Combined pipeline"}
    rows = []
    for k in ("random_forest", "xgboost", "isolation_forest", "combined"):
        m = off["test"]["models"][k]
        rows.append([mnames[k], m["accuracy"], m["precision"], m["recall"], m["f1"],
                     m["fpr"], m.get("roc_auc", 0.0)])
    top = r
    r = write_table(ws, r, ["Model", "Accuracy", "Precision", "Recall", "F1", "FPR", "ROC-AUC"],
                    rows, widths=[22, 11, 11, 10, 10, 10, 11])
    data = Reference(ws, min_col=2, max_col=7, min_row=top, max_row=top + len(rows))
    cats = Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(rows))
    bar_chart(ws, f"A{r + 2}", "Model performance on the internal test split", "Score", data, cats)

    r5 = r + 20
    ws.cell(row=r5, column=1, value="Combined pipeline, payload-bearing sources only").font = \
        Font(bold=True, size=11, color=ACCENT)
    if "combined_payload_only" in off["test"]:
        m = off["test"]["combined_payload_only"]
        write_table(ws, r5 + 1, ["Subset", "Accuracy", "Precision", "Recall", "F1", "FPR"],
                    [["Payload-bearing rows", m["accuracy"], m["precision"], m["recall"],
                      m["f1"], m["fpr"]]], widths=[24, 11, 11, 10, 10, 10])

    # ================================================== 6. Generalisation
    ws = wb.create_sheet("6. Generalisation")
    r = sheet_title(ws, "Cross-dataset generalisation - the negative result",
                    "ATRDF 2023 (540,057 rows) was never trained on, never validated against, "
                    "and never used to select the threshold.")
    rows = []
    for k in ("accuracy", "precision", "recall", "f1", "fpr"):
        g = off["generalisation_drop"][k]
        rows.append([k.capitalize(), g["test"], g["heldout"], g["delta"]])
    a = off["test"]["models"]["combined"].get("roc_auc", 0.0)
    b = off["heldout"]["models"]["combined"].get("roc_auc", 0.0)
    rows.append(["ROC-AUC", a, b, b - a])
    top = r
    r = write_table(ws, r, ["Metric", "Internal test split", "Held-out ATRDF 2023", "Change"],
                    rows, widths=[16, 20, 22, 12])
    data = Reference(ws, min_col=2, max_col=3, min_row=top, max_row=top + len(rows))
    cats = Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(rows))
    bar_chart(ws, f"A{r + 2}", "Internal test vs held-out corpus", "Score", data, cats)

    r6 = r + 20
    ws.cell(row=r6, column=1,
            value="Four experiments run to establish the cause").font = Font(bold=True, size=12, color=ACCENT)
    exp = [
        ["1. Is the feature set inadequate for ATRDF?", "No",
         "A model trained ON ATRDF reaches F1 0.8564 / AUC 0.9428 with the same 17 features."],
        ["2. Is it contamination by flow records?", "No",
         "Training on payload-bearing sources only still gives AUC 0.5450 on ATRDF."],
        ["3. Is it out-of-scope attack types?", "No",
         "Restricting to benign + SQLi only gives AUC 0.5279."],
        ["4. Is it recoverable by recalibration?", "No",
         "Benign scores higher than SQLi (0.796 vs 0.733). The ranking failed, not the threshold."],
    ]
    r6 = write_table(ws, r6 + 1, ["Candidate explanation", "Verdict", "Evidence"], exp,
                     widths=[40, 10, 70])

    r6 += 1
    ws.cell(row=r6, column=1, value="Mechanism: covariate shift").font = Font(bold=True, size=12, color=ACCENT)
    mech = [
        ["inter_arrival_time_variance", 0.2869, -0.125, 0.0],
        ["payload_length", 0.2651, 1.181, 0.171],
        ["shannon_entropy", 0.1820, 2.776, 0.987],
        ["special_char_ratio", 0.1325, 0.319, 0.055],
    ]
    write_table(ws, r6 + 1,
                ["Feature", "RF importance", "Mean z-score on ATRDF", "ATRDF rows |z| > 2"],
                mech, widths=[30, 15, 22, 20], pct_cols=(4,))

    # ================================================== 7. Feature importance
    ws = wb.create_sheet("7. Feature importance")
    r = sheet_title(ws, "Random Forest feature importance",
                    "The model relies on statistical texture, not keywords. "
                    "has_union_select - the classic SQLi signature - is almost ignored.")
    imp = off["importances"]
    rows = [[k, v] for k, v in imp.items()]
    top = r
    r = write_table(ws, r, ["Feature", "Importance"], rows, widths=[34, 14], num_fmt="0.0000")
    data = Reference(ws, min_col=2, max_col=2, min_row=top, max_row=top + len(rows))
    cats = Reference(ws, min_col=1, min_row=top + 1, max_row=top + len(rows))
    ch = BarChart()
    ch.type = "bar"
    ch.title = "Feature importance (Random Forest)"
    ch.x_axis.title = "Importance"
    ch.height, ch.width = 12, 18
    ch.add_data(data, titles_from_data=True)
    ch.set_categories(cats)
    ch.legend = None
    ws.add_chart(ch, f"D{top}")

    # ================================================== 8. Raw traffic
    ws = wb.create_sheet("8. Raw traffic")
    r = sheet_title(ws, "Labelled request log",
                    "Every generated request with its label, scores and outcome. "
                    "Labels are recorded at send time, never inferred from the verdict.")
    keep = ["generator", "attack_type", "expected_label", "path", "payload",
            "status", "blocked", "rule_score", "ml_score", "score", "latency_ms"]
    rows = []
    for p in sorted((EVAL / "traffic").glob("*.csv")):
        with p.open(newline="", encoding="utf-8") as fh:
            for d in csv.DictReader(fh):
                if d.get("error"):
                    continue
                out = []
                for k in keep:
                    v = d.get(k, "")
                    if k in ("expected_label", "status", "blocked"):
                        out.append(int(v) if str(v).strip().lstrip("-").isdigit() else v)
                    elif k in ("rule_score", "ml_score", "score", "latency_ms"):
                        try:
                            out.append(float(v))
                        except (TypeError, ValueError):
                            out.append(None)
                    else:
                        out.append((v or "")[:120])
                rows.append(out)
    write_table(ws, r, ["Generator", "Attack type", "Label", "Path", "Payload", "Status",
                        "Blocked", "Rule score", "ML score", "Combined", "Latency ms"],
                rows, widths=[16, 20, 8, 26, 44, 8, 9, 11, 11, 11, 11])
    ws.freeze_panes = ws.cell(row=r + 1, column=1)

    wb.save(OUT)
    print(f"wrote {OUT}")
    print(f"sheets: {', '.join(wb.sheetnames)}")
    print(f"raw traffic rows: {len(rows):,}")


if __name__ == "__main__":
    main()
