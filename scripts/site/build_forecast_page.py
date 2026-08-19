#!/usr/bin/env python3
"""Build docs/forecast.html — a visual General Fund forecast page.

Renders inline SVG charts (no JS, no external deps) so the page is self-contained
and works anywhere GitHub Pages serves it:
  - Financials over time: revenue vs. expenditures, and the fund-balance "plume"
    (conservative / base / optimistic band widening into the future).
  - KPIs over time: solvency ratio (plume vs. the board target band), UAB ratio
    vs. target, and bonded-debt load.

Projection scenarios come from data/normalized/gf_forecast.csv; historical anchors
are the audited ACFRs + Iowa DOM filings (hard-coded with sources). Regenerate:
    python scripts/site/build_forecast_page.py
"""
from __future__ import annotations
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FC = REPO / "data/normalized/gf_forecast.csv"
OUT = REPO / "docs/forecast.html"
GH = "https://github.com/michael480th/ICCashForecast"

# ----------------------------------------------------------------------------- #
# Data
# ----------------------------------------------------------------------------- #
def load_scen():
    d: dict[str, dict[int, dict]] = {}
    for r in csv.DictReader(open(FC)):
        d.setdefault(r["scenario"], {})[int(r["fiscal_year"])] = {
            "rev": float(r["gf_revenue"]) / 1e6,
            "exp": float(r["gf_expenditure"]) / 1e6,
            "fb": float(r["assigned_unassigned"]) / 1e6,
            "solv": float(r["solvency_pct"]),
            "uab": float(r["uab_pct"]) if r["uab_pct"] else None,
        }
    return d

SCEN = load_scen()
PROJ = list(range(2026, 2030))

# Revenue / expenditure ($M) — FY2023-2025 actual/est (PFM), FY2026-29 base scenario.
REV = {2023: 209.5, 2024: 206.5, 2025: 211.8, **{y: SCEN["base"][y]["rev"] for y in PROJ}}
EXP = {2023: 207.9, 2024: 198.2, 2025: 212.0, **{y: SCEN["base"][y]["exp"] for y in PROJ}}

# Assigned+unassigned GF fund balance ($M): history then per-scenario projection.
FB_HIST = {2023: 4.96, 2024: 14.88, 2025: 8.33}
# Solvency % history (audited FY20-23, FY24 CAR, FY25 est).
SOLV_HIST = {2020: 4.21, 2021: 6.35, 2022: 2.82, 2023: 2.45, 2024: 7.49, 2025: 4.09}
# UAB % history (Iowa DOM) + FY26 projection band.
UAB_HIST = {2020: 1.17, 2021: 1.68, 2022: 0.12, 2023: -1.21, 2024: 1.64, 2025: 2.31}
# Bonded debt outstanding ($M), audited FY20-23.
GO = {2020: 176.9, 2021: 170.6, 2022: 164.0, 2023: 156.8}
SAVE = {2020: 82.5, 2021: 74.4, 2022: 66.2, 2023: 164.7}

COL = dict(ink="#1a2230", base="#2c5fb3", hist="#1a2230", plume="#2c5fb3",
           good="#1f9d68", bad="#c64236", warn="#d9822b", grid="#e3e7ee", mut="#5b6675")


# ----------------------------------------------------------------------------- #
# SVG helpers
# ----------------------------------------------------------------------------- #
W, H, ML, MR, MT, MB = 760, 326, 56, 18, 14, 30


def ax(years, ymin, ymax):
    return dict(yrs=years, ymin=ymin, ymax=ymax)


def X(a, yr):
    lo, hi = a["yrs"][0], a["yrs"][-1]
    return ML + (yr - lo) / (hi - lo) * (W - ML - MR)


def Y(a, v):
    bot, top = H - MB, MT
    return bot - (v - a["ymin"]) / (a["ymax"] - a["ymin"]) * (bot - top)


def pts(coords):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)


def frame(a, ticks, tickfmt, divider_year=None):
    s = []
    for t in ticks:
        y = Y(a, t)
        s.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W-MR}" y2="{y:.1f}" stroke="{COL["grid"]}" stroke-width="1"/>')
        s.append(f'<text x="{ML-8}" y="{y+4:.1f}" text-anchor="end" font-size="11" fill="{COL["mut"]}">{tickfmt(t)}</text>')
    for yr in a["yrs"]:
        x = X(a, yr)
        s.append(f'<text x="{x:.1f}" y="{H-10}" text-anchor="middle" font-size="11" fill="{COL["mut"]}">’{str(yr)[2:]}</text>')
    if divider_year is not None:
        x = X(a, divider_year)
        s.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{H-MB}" stroke="#c7cedb" stroke-width="1" stroke-dasharray="3 3"/>')
        s.append(f'<text x="{x+5:.1f}" y="{MT+11}" font-size="10" fill="{COL["mut"]}">projected →</text>')
    return "".join(s)


def line(a, series, color, width=2.5, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    co = [(X(a, yr), Y(a, v)) for yr, v in series]
    return f'<polyline points="{pts(co)}" fill="none" stroke="{color}" stroke-width="{width}"{d}/>'


def dots(a, series, color, r=3.2):
    return "".join(f'<circle cx="{X(a,yr):.1f}" cy="{Y(a,v):.1f}" r="{r}" fill="{color}"/>' for yr, v in series)


def band(a, lows, highs, color, op=0.16):
    """Shaded plume polygon from lows (forward) + highs (reverse)."""
    co = [(X(a, yr), Y(a, v)) for yr, v in lows] + [(X(a, yr), Y(a, v)) for yr, v in reversed(highs)]
    return f'<polygon points="{pts(co)}" fill="{color}" fill-opacity="{op}" stroke="none"/>'


def hband(a, y0, y1, color, op=0.18):
    top, h = Y(a, y1), Y(a, y0) - Y(a, y1)
    return f'<rect x="{ML}" y="{top:.1f}" width="{W-ML-MR}" height="{h:.1f}" fill="{color}" fill-opacity="{op}"/>'


def hline(a, v, color, dash="5 4", w=1.5):
    y = Y(a, v)
    return f'<line x1="{ML}" y1="{y:.1f}" x2="{W-MR}" y2="{y:.1f}" stroke="{color}" stroke-width="{w}" stroke-dasharray="{dash}"/>'


def lbl(a, yr, v, text, color, dy=-8, anchor="middle"):
    return f'<text x="{X(a,yr):.1f}" y="{Y(a,v)+dy:.1f}" text-anchor="{anchor}" font-size="11" font-weight="700" fill="{color}">{text}</text>'


def svg(inner):
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" '
            f'style="width:100%;height:auto;display:block" font-family="inherit">{inner}</svg>')


# ----------------------------------------------------------------------------- #
# Charts
# ----------------------------------------------------------------------------- #
def chart_revexp():
    a = ax(list(range(2023, 2030)), 190, 240)
    rev = sorted(REV.items()); exp = sorted(EXP.items())
    s = [frame(a, [190, 200, 210, 220, 230, 240], lambda t: f"${t:.0f}M", 2026)]
    # shade gap between the two lines
    co = [(X(a, yr), Y(a, v)) for yr, v in rev] + [(X(a, yr), Y(a, v)) for yr, v in reversed(exp)]
    s.append(f'<polygon points="{pts(co)}" fill="{COL["bad"]}" fill-opacity="0.07"/>')
    s.append(line(a, exp, COL["bad"], 2.5))
    s.append(line(a, rev, COL["good"], 2.5))
    s.append(dots(a, rev, COL["good"])); s.append(dots(a, exp, COL["bad"]))
    s.append(lbl(a, 2029, REV[2029], "Revenue", COL["good"], -10))
    s.append(lbl(a, 2029, EXP[2029], "Expenses", COL["bad"], 16))
    s.append(f'<text x="{X(a,2026):.1f}" y="{Y(a,225)+1:.1f}" text-anchor="middle" font-size="10.5" fill="{COL["bad"]}" font-weight="700">FY26: −$6M</text>')
    return svg("".join(s))


def chart_plume(hist, scen_key, ax_args, ticks, tickfmt, target=None, floor=None, zero=False, unit=""):
    a = ax(*ax_args)
    junction = max(hist)  # last historical year = plume origin
    base = [(junction, hist[junction])] + [(y, SCEN["base"][y][scen_key]) for y in PROJ]
    lows = [(junction, hist[junction])] + [(y, SCEN["conservative"][y][scen_key]) for y in PROJ]
    highs = [(junction, hist[junction])] + [(y, SCEN["optimistic"][y][scen_key]) for y in PROJ]
    s = [frame(a, ticks, tickfmt, 2026)]
    if target:
        s.append(hband(a, target[0], target[1], COL["good"]))
        s.append(f'<text x="{W-MR-4}" y="{Y(a,target[1])+13:.1f}" text-anchor="end" font-size="10" fill="{COL["good"]}" font-weight="700">board target {target[0]}–{target[1]}{unit}</text>')
    if floor is not None:
        s.append(hline(a, floor, COL["warn"]))
        s.append(f'<text x="{W-MR-4}" y="{Y(a,floor)-5:.1f}" text-anchor="end" font-size="10" fill="{COL["warn"]}" font-weight="700">{floor}{unit} floor</text>')
    if zero:
        s.append(hline(a, 0, "#aab2c0", "2 3", 1))
    s.append(band(a, lows, highs, COL["plume"]))
    s.append(line(a, highs, COL["base"], 1, "4 3"))
    s.append(line(a, lows, COL["base"], 1, "4 3"))
    s.append(line(a, base, COL["base"], 2.8))
    s.append(line(a, sorted(hist.items()), COL["hist"], 2.8))
    s.append(dots(a, sorted(hist.items()), COL["hist"]))
    s.append(dots(a, base, COL["base"]))
    # endpoint labels for the spread
    fy = 2029
    s.append(lbl(a, fy, SCEN["optimistic"][fy][scen_key], tickfmt(SCEN["optimistic"][fy][scen_key]), COL["good"], -8, "end"))
    s.append(lbl(a, fy, SCEN["base"][fy][scen_key], tickfmt(SCEN["base"][fy][scen_key]), COL["base"], 4, "end"))
    s.append(lbl(a, fy, SCEN["conservative"][fy][scen_key], tickfmt(SCEN["conservative"][fy][scen_key]), COL["bad"], 14, "end"))
    return svg("".join(s))


def chart_uab():
    a = ax(list(range(2020, 2027)), -4, 11)
    s = [frame(a, [-4, 0, 5, 10], lambda t: f"{t:.0f}%", 2026)]
    s.append(hband(a, 5, 10, COL["good"]))
    s.append(f'<text x="{W-MR-4}" y="{Y(a,10)+13:.1f}" text-anchor="end" font-size="10" fill="{COL["good"]}" font-weight="700">board target 5–10%</text>')
    s.append(hline(a, 0, "#aab2c0", "2 3", 1))
    hist = sorted(UAB_HIST.items())
    s.append(line(a, hist, COL["hist"], 2.8))
    s.append(dots(a, hist, COL["hist"]))
    # FY26 projection band point (cons -2.40 / base -1.39 / opt 1.65)
    c, b, o = SCEN["conservative"][2026]["uab"], SCEN["base"][2026]["uab"], SCEN["optimistic"][2026]["uab"]
    x = X(a, 2026)
    s.append(f'<line x1="{x:.1f}" y1="{Y(a,o):.1f}" x2="{x:.1f}" y2="{Y(a,c):.1f}" stroke="{COL["plume"]}" stroke-width="6" stroke-opacity="0.25" stroke-linecap="round"/>')
    s.append(f'<circle cx="{x:.1f}" cy="{Y(a,b):.1f}" r="3.6" fill="{COL["base"]}"/>')
    s.append(lbl(a, 2026, b, f"FY26 ~{b:.1f}%", COL["base"], 18))
    s.append(lbl(a, 2023, UAB_HIST[2023], "−1.2%", COL["bad"], 16))
    return svg("".join(s))


def chart_debt():
    a = ax(list(range(2020, 2024)), 0, 200)
    s = [frame(a, [0, 50, 100, 150, 200], lambda t: f"${t:.0f}M")]
    go = sorted(GO.items()); sv = sorted(SAVE.items())
    s.append(line(a, go, COL["base"], 2.5)); s.append(dots(a, go, COL["base"]))
    s.append(line(a, sv, COL["warn"], 2.5)); s.append(dots(a, sv, COL["warn"]))
    s.append(lbl(a, 2020, GO[2020], "GO bonds", COL["base"], -10, "start"))
    s.append(lbl(a, 2023, SAVE[2023], "SAVE bonds", COL["warn"], -10, "end"))
    s.append(f'<text x="{X(a,2023):.1f}" y="{Y(a,SAVE[2023])+18:.1f}" text-anchor="end" font-size="10" fill="{COL["warn"]}">new issuance</text>')
    return svg("".join(s))


# ----------------------------------------------------------------------------- #
# Page
# ----------------------------------------------------------------------------- #
NAV = (f'<nav class="topnav"><a class="brand" href="../index.html">ICCashForecast</a>'
       f'<div class="links"><a href="../index.html">Bond Rating</a>'
       f'<a href="forecast.html" aria-current=page>Forecast</a>'
       f'<a href="liquidity.html">Liquidity</a><a href="kpi_scorecard.html">KPI Scorecard</a>'
       f'<a href="board_materials_triage.html">Board Materials</a>'
       f'<a href="{GH}">GitHub ↗</a></div></nav>')


def legend():
    return ('<div class="legend">'
            '<span><i style="background:#1a2230"></i>Actual / audited</span>'
            '<span><i style="background:#2c5fb3"></i>Base case (PFM)</span>'
            '<span><i class="bandkey"></i>Range: conservative ↔ optimistic</span>'
            '<span><i style="background:#e7f6ee;border:1px solid #bfe6cf"></i>Board target</span>'
            '</div>')


def build():
    base_css = (REPO / "docs/site.css").read_text(encoding="utf-8")
    page = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ICCSD General Fund Forecast — ICCashForecast</title>
<style>
{base_css}
.chart{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px 8px;margin:14px 0;
  box-shadow:0 1px 2px rgba(20,30,50,.04)}}
.chart h3{{margin:0 0 2px;color:var(--ink);text-transform:none;letter-spacing:0;font-size:16px}}
.chart .sub{{color:var(--muted);font-size:13px;margin:0 0 8px}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:#384356;margin:6px 0 18px}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:inline-block}}
.legend i.bandkey{{background:linear-gradient(#2c5fb3,#2c5fb3);opacity:.22;border:1px solid #2c5fb3}}
.two-up{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.two-up .chart{{margin:0}}
@media(max-width:720px){{.two-up{{grid-template-columns:1fr}}}}
</style></head>
<body>
{NAV}
<header class="hero"><div class="wrap">
<p class="kicker">ICCashForecast &middot; unofficial analysis</p>
<h1>ICCSD General Fund Forecast</h1>
<p>The district&rsquo;s finances over time, and this model&rsquo;s range of expected outcomes.</p>
</div></header>
<div class="wrap">

<div class="callout"><div>The shape of it</div>
<p style="margin:6px 0 0">ICCSD runs a <b>structural operating deficit</b> on PFM&rsquo;s numbers — expenses pull
ahead of revenue — so the General Fund&rsquo;s cushion stays thin and its KPIs sit <b>below the board&rsquo;s
own targets through FY2029</b>. The shaded plume shows how the range widens the further out we look:
even the optimistic edge only re-enters the solvency target late, while the conservative edge goes negative.</p></div>

{legend()}

<h2>Financials over time</h2>

<div class="chart"><h3>Revenue vs. expenditures</h3>
<p class="sub">General Fund, $ millions. FY2023&ndash;25 actual/estimated; FY2026&ndash;29 base case (PFM).</p>
{chart_revexp()}</div>

<div class="chart"><h3>General Fund balance &mdash; the plume</h3>
<p class="sub">Assigned + unassigned fund balance, $ millions. Band = conservative to optimistic.</p>
{chart_plume(FB_HIST, "fb", (list(range(2023,2030)), -18, 42), [-15,0,15,30], lambda t:f"${t:.0f}M", zero=True, unit="M")}</div>

<h2>Key financial indicators (KPIs) over time</h2>

<div class="chart"><h3>Solvency ratio vs. board target</h3>
<p class="sub">Unrestricted GF balance &divide; (revenue &minus; AEA), per board policy 701.5R1. Target 10&ndash;15%, 5% floor.</p>
{chart_plume(SOLV_HIST, "solv", (list(range(2020,2030)), -8, 18), [-5,0,5,10,15], lambda t:f"{t:.0f}%", target=(10,15), floor=5, zero=True, unit="%")}</div>

<div class="two-up">
<div class="chart"><h3>Unspent Authorized Budget</h3>
<p class="sub">Spending-authority cushion. Target 5&ndash;10%.</p>
{chart_uab()}</div>
<div class="chart"><h3>Bonded debt load</h3>
<p class="sub">Outstanding GO + SAVE bonds, $M (audited).</p>
{chart_debt()}</div>
</div>

<h2>The numbers</h2>
<table>
<tr><th>FY2026 (base)</th><th>Conservative</th><th>Base</th><th>Optimistic</th></tr>
<tr><td>Operating result</td><td>−${abs(SCEN['conservative'][2026]['rev']-SCEN['conservative'][2026]['exp']):.1f}M</td>
<td>−${abs(SCEN['base'][2026]['rev']-SCEN['base'][2026]['exp']):.1f}M</td>
<td>+${SCEN['optimistic'][2026]['rev']-SCEN['optimistic'][2026]['exp']:.1f}M</td></tr>
<tr><td>Solvency ratio</td><td>{SCEN['conservative'][2026]['solv']:.1f}%</td><td><b>{SCEN['base'][2026]['solv']:.1f}%</b></td><td>{SCEN['optimistic'][2026]['solv']:.1f}%</td></tr>
<tr><td>UAB ratio</td><td>{SCEN['conservative'][2026]['uab']:.1f}%</td><td><b>{SCEN['base'][2026]['uab']:.1f}%</b></td><td>{SCEN['optimistic'][2026]['uab']:.1f}%</td></tr>
<tr><td>FY2029 solvency</td><td>{SCEN['conservative'][2029]['solv']:.1f}%</td><td><b>{SCEN['base'][2029]['solv']:.1f}%</b></td><td>{SCEN['optimistic'][2029]['solv']:.1f}%</td></tr>
</table>

<h2>How to read this</h2>
<div class="card"><ul>
<li><b>Base case</b> is reconciled to PFM&rsquo;s own 7-year General Fund cash-flow model (the district advisor&rsquo;s projection).</li>
<li><b>The plume</b> widens because small annual surplus/deficit differences compound on a thin fund balance &mdash; by FY2029 the outcomes range from deeply negative to a full recovery.</li>
<li><b>Targets</b> are the board&rsquo;s own (policy 701.5R1): solvency 10&ndash;15% (5% floor), UAB 5&ndash;10%. Both sit above where the forecast lands.</li>
<li><b>Debt</b> is shown through the latest audited year (FY2023); GO bonds are being paid down while SAVE jumped on a FY2023 issuance.</li>
</ul></div>

<footer>
<p><b>Sources.</b> data/normalized/gf_forecast.csv (this model); PFM Financial Advisors board
presentations; ICCSD audited ACFRs (FY2020&ndash;2023); Iowa DOM filings. FY2024&ndash;2029 figures are
unaudited estimates/projections carrying material uncertainty &mdash; that uncertainty is the plume.</p>
<p class="src"><b>Disclaimer.</b> Unofficial, illustrative estimate. Not investment advice and not
affiliated with ICCSD or PFM. Regenerate with <code>python scripts/site/build_forecast_page.py</code>.</p>
</footer>
</div></body></html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(page):,} bytes)")


if __name__ == "__main__":
    build()
