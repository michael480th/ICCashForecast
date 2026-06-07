#!/usr/bin/env python3
"""Month-by-month General Fund liquidity (cash) forecast through June 2027.

ICCSD's risk is timing: property taxes arrive in two big waves (October and
April) while spending is steady, so cash draws down in between. This projects
month-end GF cash from the latest known balance, applying the FY2025 monthly
seasonality (extracted into monthly_actuals.csv) scaled to each scenario's annual
revenue/expenditure (from gf_forecast.csv), and finds the low points.

Cash basis: month-end cash = prior cash + (monthly revenue - monthly expenditure).
This is operating flow only; known one-time events (property-sale proceeds,
interfund loans) are not yet layered in and would lift specific months.

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


def project(rev_share, exp_share, start_dt, start_cash, annuals):
    """Return {scenario: [(year, month, cash_end), ...]} from the month after
    start_dt through June 2027."""
    series = {}
    for scen, years in annuals.items():
        cash = start_cash
        pts = []
        # remaining FY2026 months (after start_dt) then all FY2027
        plan = [(2026, m) for m in FY_MONTHS
                if date(2026 if m <= 6 else 2025, m, 1) > start_dt] + \
               [(2027, m) for m in FY_MONTHS]
        for fy, m in plan:
            a = years.get(fy) or years[max(years)]
            flow = a["rev"] * rev_share[m] - a["exp"] * exp_share[m]
            cash += flow
            cal_year = fy - 1 if m >= 7 else fy
            pts.append((cal_year, m, round(cash)))
        series[scen] = pts
    return series


def main():
    rev_share, exp_share = load_seasonality()
    start_dt, start_cash = load_start_cash()
    annuals = load_annuals()
    series = project(rev_share, exp_share, start_dt, start_cash, annuals)

    # tidy CSV
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["calendar_month", "scenario", "gf_cash_month_end"])
        for scen, pts in series.items():
            for cy, m, c in pts:
                w.writerow([f"{cy}-{m:02d}", scen, c])

    # troughs
    troughs = {scen: min(pts, key=lambda x: x[2]) for scen, pts in series.items()}

    L = ["# ICCSD General Fund monthly liquidity forecast\n",
         f"Month-end GF cash projected from the latest known balance "
         f"(**${start_cash/1e6:.1f}M** on {start_dt.isoformat()}) through June 2027, "
         f"applying FY2025 monthly seasonality scaled to each scenario. Operating "
         f"flows only — known one-time events (property-sale proceeds, interfund "
         f"loans) are not yet layered in.\n",
         "> ICCSD collects property tax in two waves (**October** and **April**); "
         "cash draws down in between and drops on the **June** payroll/accrual "
         "spike. The low points fall in **early fall**, before the October wave.\n",
         "## Projected cash low points (troughs)\n",
         "| Scenario | Trough month | GF cash at trough |",
         "|---|---|---|"]
    for scen in ["conservative", "base", "optimistic"]:
        cy, m, c = troughs[scen]
        flag = " ⚠️ near/below zero" if c < 2_000_000 else ""
        L.append(f"| {scen} | {MONTH_ABBR[m]} {cy} | **${c/1e6:.1f}M**{flag} |")

    L.append("\n## Month-end cash trajectory (base, with band)\n")
    L.append("| Month | Conservative | Base | Optimistic |")
    L.append("|---|---|---|---|")
    months = [(cy, m) for cy, m, _ in series["base"]]
    lut = {scen: {(cy, m): c for cy, m, c in pts} for scen, pts in series.items()}
    for cy, m in months:
        lo = lut["conservative"][(cy, m)] / 1e6
        bs = lut["base"][(cy, m)] / 1e6
        hi = lut["optimistic"][(cy, m)] / 1e6
        star = " ◀ trough" if (cy, m) == (troughs["base"][0], troughs["base"][1]) else ""
        L.append(f"| {MONTH_ABBR[m]} {cy} | {lo:.1f} | **{bs:.1f}** | {hi:.1f} |{star}")

    cy, m, c = troughs["base"]
    cyc, mc, cc = troughs["conservative"]
    L.append(f"\n## Read\n")
    L.append(f"- **Base-case low point: ${c/1e6:.1f}M in {MONTH_ABBR[m]} {cy}** — the "
             f"early-fall trough before October property taxes arrive.")
    L.append(f"- **Conservative low point: ${cc/1e6:.1f}M in {MONTH_ABBR[mc]} {cyc}**"
             f"{' — effectively out of cash' if cc < 2_000_000 else ''}. A single soft "
             f"revenue year turns the timing squeeze into a genuine liquidity event.")
    L.append(f"- This is why the property-sale proceeds and interfund-loan timing "
             f"matter: they land near these troughs and are the levers that keep cash "
             f"positive. Layering those one-time events in is the next refinement.\n")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"Liquidity forecast -> {OUT_CSV.relative_to(REPO)}, {OUT_MD.relative_to(REPO)}")
    for scen in ["conservative", "base", "optimistic"]:
        cy, m, c = troughs[scen]
        print(f"  {scen:<12} trough: {MONTH_ABBR[m]} {cy}  ${c/1e6:.1f}M")


if __name__ == "__main__":
    main()
