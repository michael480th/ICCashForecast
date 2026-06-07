#!/usr/bin/env python3
"""Month-by-month General Fund liquidity (cash) forecast through June 2027.

ICCSD's risk is timing: property taxes arrive in two big waves (October and
April) while spending is steady, so cash draws down in between. This projects
month-end GF cash from the latest known balance, applying the FY2025 monthly
seasonality (extracted into monthly_actuals.csv) scaled to each scenario's annual
revenue/expenditure (from gf_forecast.csv).

Two trajectories are produced:
  - operating only: revenue - expenditure each month.
  - with interfund obligations: also applies the dated interfund cash flows in
    known_events.csv — notably the $7.32M the GF lends SAVE in May 2026 (out of
    GF until SAVE repays by Oct 1) and the $10M the GF must repay the Health
    Insurance fund by Oct 1, 2026. These land right around the fall trough.

Cash basis: month-end cash = prior cash + monthly operating flow + dated events.
Uncertain events with no amount (e.g. the 1725 N. Dodge sale proceeds) are NOT in
the base lines and are discussed as upside levers.

Outputs: data/normalized/monthly_liquidity.csv, docs/liquidity.md
"""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONTHLY = REPO / "data/normalized/monthly_actuals.csv"
CASHBAL = REPO / "data/normalized/cash_balances.csv"
FORECAST = REPO / "data/normalized/gf_forecast.csv"
EVENTS = REPO / "data/normalized/known_events.csv"
OUT_CSV = REPO / "data/normalized/monthly_liquidity.csv"
OUT_MD = REPO / "docs/liquidity.md"

FY_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]  # July..June
MONTH_ABBR = {7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
              1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun"}


def load_seasonality():
    """FY2025 monthly revenue & expenditure shares, keyed by calendar month."""
    rev = {m: 0.0 for m in FY_MONTHS}
    exp = {m: 0.0 for m in FY_MONTHS}
    for r in csv.DictReader(open(MONTHLY)):
        if r["amount"] in ("", "None"):
            continue
        mo = int(r["month"].split("-")[1])
        (rev if r["type"] == "revenue" else exp)[mo] += float(r["amount"])
    tr, te = sum(rev.values()), sum(exp.values())
    return {m: rev[m] / tr for m in FY_MONTHS}, {m: exp[m] / te for m in FY_MONTHS}


def load_start_cash():
    """Latest GF (fund 10) cash position = projection start point."""
    rows = [r for r in csv.DictReader(open(CASHBAL)) if r["fund_code"] == "10"]
    r = max(rows, key=lambda x: x["as_of_date"])
    return date.fromisoformat(r["as_of_date"]), float(r["total_cash_investments"])


def load_annuals():
    """Per-scenario annual GF revenue/expenditure for FY2026 and FY2027."""
    out: dict[str, dict[int, dict]] = {}
    for r in csv.DictReader(open(FORECAST)):
        out.setdefault(r["scenario"], {})[int(r["fiscal_year"])] = {
            "rev": float(r["gf_revenue"]), "exp": float(r["gf_expenditure"])}
    return out


def load_events():
    """GF (fund 10) dated cash deltas keyed by (calendar_year, month).
    Inflows positive, outflows negative; rows without an amount are skipped."""
    deltas: dict[tuple[int, int], float] = {}
    for r in csv.DictReader(open(EVENTS)):
        if r["fund_code"] != "10" or not r["amount"]:
            continue
        d = date.fromisoformat(r["event_date"])
        amt = float(r["amount"]) * (1 if r["direction"] == "inflow" else -1)
        deltas[(d.year, d.month)] = deltas.get((d.year, d.month), 0.0) + amt
    return deltas


def project(rev_share, exp_share, start_dt, start_cash, annuals, events):
    """{scenario: [(year, month, cash_operating, cash_with_events), ...]}."""
    series = {}
    for scen, years in annuals.items():
        cash_op = cash_all = start_cash
        pts = []
        plan = [(2026, m) for m in FY_MONTHS
                if date(2026 if m <= 6 else 2025, m, 1) > start_dt] + \
               [(2027, m) for m in FY_MONTHS]
        for fy, m in plan:
            a = years.get(fy) or years[max(years)]
            flow = a["rev"] * rev_share[m] - a["exp"] * exp_share[m]
            cal_year = fy - 1 if m >= 7 else fy
            cash_op += flow
            cash_all += flow + events.get((cal_year, m), 0.0)
            pts.append((cal_year, m, round(cash_op), round(cash_all)))
        series[scen] = pts
    return series


def main():
    rev_share, exp_share = load_seasonality()
    start_dt, start_cash = load_start_cash()
    annuals = load_annuals()
    events = load_events()
    series = project(rev_share, exp_share, start_dt, start_cash, annuals, events)

    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["calendar_month", "scenario", "gf_cash_operating",
                    "gf_cash_with_interfund"])
        for scen, pts in series.items():
            for cy, m, op, al in pts:
                w.writerow([f"{cy}-{m:02d}", scen, op, al])

    # troughs: with-interfund line is the real available cash
    tr = {s: min(pts, key=lambda x: x[3]) for s, pts in series.items()}
    tr_op = {s: min(pts, key=lambda x: x[2]) for s, pts in series.items()}

    L = ["# ICCSD General Fund monthly liquidity forecast\n",
         f"Month-end GF cash projected from the latest known balance "
         f"(**${start_cash/1e6:.1f}M** on {start_dt.isoformat()}) through June 2027, "
         f"applying FY2025 monthly seasonality scaled to each scenario, then "
         f"overlaying the dated interfund cash flows the board has authorized.\n",
         f"> **Two facts about that ${start_cash/1e6:.0f}M starting balance:** it "
         f"already includes a **$10M loan from the Health Insurance fund** (received "
         f"8/2025, due back by 10/1/2026), and in **May 2026 the GF lends SAVE "
         f"$7.32M** that doesn't return until Oct 1. Real available cash over the "
         f"summer is lower than the headline.\n",
         "> Property tax arrives in two waves (**October**, **April**); cash troughs "
         "in **early fall** — exactly the **September 2026** risk the district's own "
         "COO memo flags.\n",
         "## Projected cash low points (troughs)\n",
         "| Scenario | Operating only | **With interfund obligations** |",
         "|---|---|---|"]
    for s in ["conservative", "base", "optimistic"]:
        oy, om, ooc, _ = tr_op[s]
        cy, cm, _, cc = tr[s]
        flag = " 🔴 **negative**" if cc < 0 else (" ⚠️" if cc < 2e6 else "")
        L.append(f"| {s} | ${ooc/1e6:.1f}M ({MONTH_ABBR[om]} {oy}) | "
                 f"**${cc/1e6:.1f}M ({MONTH_ABBR[cm]} {cy})**{flag} |")

    L += ["\n## Month-end cash *with interfund obligations* (base, with band)\n",
          "| Month | Conservative | Base | Optimistic |", "|---|---|---|---|"]
    lut = {s: {(cy, m): al for cy, m, op, al in pts} for s, pts in series.items()}
    for cy, m, _, _ in series["base"]:
        lo = lut["conservative"][(cy, m)] / 1e6
        bs = lut["base"][(cy, m)] / 1e6
        hi = lut["optimistic"][(cy, m)] / 1e6
        star = " ◀ trough" if (cy, m) == (tr["base"][0], tr["base"][1]) else ""
        L.append(f"| {MONTH_ABBR[m]} {cy} | {lo:.1f} | **{bs:.1f}** | {hi:.1f} |{star}")

    by, bm, _, bc = tr["base"]
    cyy, cmm, _, ccc = tr["conservative"]
    L += ["\n## Read\n",
          f"- **With the interfund loans, the base case bottoms at ${bc/1e6:.1f}M "
          f"in {MONTH_ABBR[bm]} {by}**" +
          (" — the General Fund goes negative" if bc < 0 else "") +
          f", because the $7.32M lent to SAVE is still out when fall spending peaks.",
          f"- **Conservative: ${ccc/1e6:.1f}M ({MONTH_ABBR[cmm]} {cyy})** — a clear "
          f"cash shortfall. This is why the board authorized a **$3M anticipatory "
          f"warrant** (a short-term borrowing backstop, undrawn as of spring 2026).",
          "- **The levers that close the gap:** (1) SAVE repays the $7.32M by Oct 1; "
          "(2) the **1725 N. Dodge sale proceeds** land in the GF (amount TBD — the "
          "COO memo warns September gets harder if it doesn't close); (3) **postponing "
          "the $10M Insurance repayment** past June 30 preserves liquidity (at the "
          "cost of an FY26 audit note); (4) the $3M warrant.",
          "- **Bottom line:** ICCSD can likely cover the fall trough, but only by "
          "actively managing interfund timing and one-time inflows — there is little "
          "to no margin. That is the liquidity-timing crunch, quantified.\n"]
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"Liquidity forecast -> {OUT_CSV.relative_to(REPO)}, {OUT_MD.relative_to(REPO)}")
    for s in ["conservative", "base", "optimistic"]:
        cy, m, _, cc = tr[s]
        oy, om, ooc, _ = tr_op[s]
        print(f"  {s:<12} operating ${ooc/1e6:5.1f}M ({MONTH_ABBR[om]} {oy})"
              f"   with interfund ${cc/1e6:6.1f}M ({MONTH_ABBR[m]} {cy})")


if __name__ == "__main__":
    main()
