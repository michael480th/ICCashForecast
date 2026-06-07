#!/usr/bin/env python3
"""Forward-looking General Fund forecast for ICCSD: FY2026-FY2027.

Projects the General Fund operating result, fund balance, and the two board-policy
KPIs (solvency ratio and Unspent Authorized Budget ratio) under three scenarios —
conservative / base / optimistic — so genuinely uncertain quantities are shown as
a band rather than a false point estimate (per the project's "range what you're
uncertain of" guidance).

KPI definitions follow board policy 701.5R1:
  solvency_ratio = (assigned + unassigned GF fund balance) / (GF revenue - AEA flow-through)
  uab_ratio      = (max authorized budget - GF expenditures) / max authorized budget

ANCHORS (hard data — see source notes):
  - Assigned+unassigned GF fund balance: FY2020-2023 audited ACFRs (assigned=$0,
    so = unassigned); FY2024 = $14,881,750 from the FY2024 Certified Annual Report
    (Iowa DOM cash-reserve-levy worksheet). FY2024's rebuild from the FY2022-23
    trough is the single most important driver of the forward path.
  - GF revenue/expenditure: FY2020-2023 audited; FY2025 from the FY26 Q2 report's
    prior-year totals; FY2026 from the FY26 budget (Q3 report).
  - AEA flow-through: Iowa DOM (FY2023-2025 actual; FY2026-2027 grown +2%/yr).
  - UAB: FY2025 actual (max auth $217.88M, expenditures $212.85M -> 2.31%).

CAVEATS: FY2024-2026 figures are unaudited (no ACFR issued for FY2024/2025/2026);
the assigned+unassigned roll-forward assumes the net operating result accrues to
assigned+unassigned balances; the UAB projection is the most sensitive (depends on
the not-yet-final FY2026/2027 authorized budget) and is modeled from ICCSD's
observed spend rate.
"""
from __future__ import annotations
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT_CSV = REPO / "data/normalized/gf_forecast.csv"
OUT_MD = REPO / "docs/forecast.md"

TARGET_SOLV = (10.0, 15.0, 5.0)   # low, high, floor
TARGET_UAB = (5.0, 10.0, None)

# ---- Hard anchors -------------------------------------------------------- #
AU = {2020: 6_876_239, 2021: 11_653_470, 2022: 5_356_550, 2023: 4_960_343,
      2024: 14_881_750}            # assigned+unassigned GF fund balance ($)
REV = {2020: 169_739_238, 2021: 190_498_914, 2022: 196_760_462,
       2023: 209_488_033, 2025: 208_583_924, 2026: 218_169_788}
EXP = {2023: 207_876_297, 2025: 208_850_928, 2026: 212_143_412}
AEA = {2023: 7_118_887, 2024: 7_937_307, 2025: 8_064_107,
       2026: 8_225_000, 2027: 8_400_000}
SOLV_AUDITED = {2020: 4.21, 2021: 6.35, 2022: 2.82, 2023: 2.45}
UAB25 = dict(max_auth=217_878_973, exp=212_847_380, uab=5_031_593)  # FY2025

# ---- Scenario levers ----------------------------------------------------- #
# (rev vs FY26 budget, exp vs FY26 budget, FY27 rev growth, FY27 exp growth,
#  FY26 spend-rate = exp/max_auth, FY26 max_auth growth over FY25)
SCEN = {
    "conservative": dict(r26=0.978, e26=1.009, g27r=0.020, g27e=0.035, spend=0.990, auth=1.025),
    "base":         dict(r26=1.000, e26=1.000, g27r=0.030, g27e=0.030, spend=0.975, auth=1.030),
    "optimistic":   dict(r26=1.004, e26=0.981, g27r=0.040, g27e=0.025, spend=0.950, auth=1.035),
}


def solvency(au, rev, fy):
    return round(au / (rev - AEA[fy]) * 100, 2)


def status(v, tgt):
    lo, hi, fl = tgt
    if v >= lo:
        return "on_target" if v <= hi else "above_target"
    if fl is not None and v < fl:
        return "below_floor"
    return "below_target"


def project():
    rows = []
    # FY2025 assigned+unassigned: roll FY2024 forward by FY2025 operating result.
    au25 = AU[2024] + (REV[2025] - EXP[2025])
    for name, s in SCEN.items():
        rev26 = REV[2026] * s["r26"]
        exp26 = EXP[2026] * s["e26"]
        au26 = au25 + (rev26 - exp26)
        rev27 = rev26 * (1 + s["g27r"])
        exp27 = exp26 * (1 + s["g27e"])
        au27 = au26 + (rev27 - exp27)
        max_auth26 = UAB25["max_auth"] * s["auth"]
        exp_uab26 = max_auth26 * s["spend"]          # UAB-basis expenditures
        uab26 = max_auth26 - exp_uab26
        for fy, rev, exp, au, ma, ub in [
            (2026, rev26, exp26, au26, max_auth26, uab26),
            (2027, rev27, exp27, au27, None, None),
        ]:
            sv = solvency(au, rev, fy)
            row = dict(fiscal_year=fy, scenario=name,
                       gf_revenue=round(rev), gf_expenditure=round(exp),
                       operating_result=round(rev - exp),
                       assigned_unassigned=round(au),
                       solvency_pct=sv, solvency_status=status(sv, TARGET_SOLV),
                       uab_pct=(round(ub / ma * 100, 2) if ma else ""),
                       uab_status=(status(ub / ma * 100, TARGET_UAB) if ma else ""))
            rows.append(row)
    return rows, au25


def write_csv(rows):
    fields = ["fiscal_year", "scenario", "gf_revenue", "gf_expenditure",
              "operating_result", "assigned_unassigned", "solvency_pct",
              "solvency_status", "uab_pct", "uab_status"]
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(rows)


def band(rows, fy, key):
    vals = [r[key] for r in rows if r["fiscal_year"] == fy and r[key] != ""]
    base = next(r[key] for r in rows if r["fiscal_year"] == fy and r["scenario"] == "base")
    return min(vals), base, max(vals)


def write_md(rows, au25):
    L = []
    A = L.append
    A("# ICCSD General Fund forward forecast (FY2026–FY2027)\n")
    A("Forecast of the General Fund and its two board-policy KPIs. Uncertain "
      "quantities are shown as a **band** across conservative / base / optimistic "
      "scenarios. KPI definitions per board policy 701.5R1.\n")
    A("> **Bases & caveats.** FY2024–2026 are unaudited (no ACFR issued yet). The "
      "FY2024 assigned+unassigned balance ($14.88M, FY2024 Certified Annual Report) "
      "shows the fund balance rebuilt from the FY2022–23 trough — the key driver of "
      "the forward path. The UAB projection is the most sensitive (depends on the "
      "not-yet-final authorized budget) and is modeled from ICCSD's observed spend "
      "rate; treat its band as wide.\n")

    A("## Solvency ratio — trajectory vs. board target (10–15%, 5% floor)\n")
    A("| Fiscal year | Conservative | Base | Optimistic |")
    A("|---|---|---|---|")
    for fy in (2020, 2021, 2022, 2023):
        A(f"| FY{fy} (audited) | — | {SOLV_AUDITED[fy]:.2f}% | — |")
    A(f"| FY2024 (CAR, est.) | — | ~{solvency(AU[2024], 206_000_000, 2024):.1f}%* | — |")
    A(f"| FY2025 (est.) | — | ~{solvency(au25, REV[2025], 2025):.1f}% | — |")
    for fy in (2026, 2027):
        lo, base, hi = band(rows, fy, "solvency_pct")
        A(f"| **FY{fy} (proj.)** | {lo:.1f}% | **{base:.1f}%** | {hi:.1f}% |")
    A("\n*FY2024 denominator uses an estimated GF revenue (~$206M); FY24/25 revenue "
      "is not separately reported in audited form.*\n")

    A("## Unspent Authorized Budget ratio — vs. board target (5–10%)\n")
    A("| Fiscal year | Conservative | Base | Optimistic |")
    A("|---|---|---|---|")
    A("| FY2025 (actual) | — | 2.31% | — |")
    lo, base, hi = band(rows, 2026, "uab_pct")
    A(f"| **FY2026 (proj.)** | {lo:.1f}% | **{base:.1f}%** | {hi:.1f}% |")

    A("\n## How the year ends — the bottom line\n")
    lo, sb, hi = band(rows, 2026, "solvency_pct")
    obase = next(r["operating_result"] for r in rows if r["fiscal_year"] == 2026 and r["scenario"] == "base")
    oc = next(r["operating_result"] for r in rows if r["fiscal_year"] == 2026 and r["scenario"] == "conservative")
    oo = next(r["operating_result"] for r in rows if r["fiscal_year"] == 2026 and r["scenario"] == "optimistic")
    aub = next(r["assigned_unassigned"] for r in rows if r["fiscal_year"] == 2026 and r["scenario"] == "base")
    A(f"- **FY2026 operating result:** base **+${obase/1e6:.1f}M** (band ${oc/1e6:+.1f}M to ${oo/1e6:+.1f}M).")
    A(f"- **FY2026 assigned+unassigned fund balance:** ~${aub/1e6:.1f}M (base).")
    A(f"- **FY2026 solvency ratio:** base **{sb:.1f}%** (band {lo:.1f}–{hi:.1f}%) — "
      f"recovering toward the 10–15% target but not yet inside it; above the 5% floor "
      f"in the base/optimistic cases, near it in the conservative case.")
    A(f"- **FY2026 UAB ratio:** ~{base:.1f}% — still **below** the 5–10% target, "
      f"consistent with ICCSD ranking last among large Iowa peers.\n")
    A("**Read:** after the FY2020–23 trough, the General Fund has been rebuilding. "
      "The base case has solvency climbing back toward — but not into — the board's "
      "target band by FY2027, while the spending-authority cushion (UAB) stays below "
      "target. The conservative band shows how a single soft revenue year (property "
      "tax / state aid timing) pulls solvency back toward the 5% floor — the core "
      "liquidity-timing risk.\n")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


rows, au25 = project()
write_csv(rows)
write_md(rows, au25)
print(f"GF forecast: {len(rows)} scenario-rows -> {OUT_CSV.relative_to(REPO)}")
print(f"  -> {OUT_MD.relative_to(REPO)}")
for fy in (2026, 2027):
    lo, b, hi = band(rows, fy, "solvency_pct")
    print(f"  FY{fy} solvency: base {b:.1f}%  band {lo:.1f}-{hi:.1f}%")
