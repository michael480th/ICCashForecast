#!/usr/bin/env python3
"""Build the ICCashForecast GitHub Pages site into docs/.

Converts the markdown analysis reports to styled, self-contained HTML pages
(shared docs/site.css), generates the landing page (index.html), and drops a
.nojekyll marker so GitHub Pages serves the files as-is. The hand-built
bond_rating_assessment.html is linked from the nav (it shares site.css).

Serve GitHub Pages from the `docs/` folder. Regenerate with:
    python scripts/site/build_site.py
"""
from __future__ import annotations
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
GH = "https://github.com/michael480th/ICCashForecast"

# Markdown reports to convert -> (output html, nav label, hero subtitle)
REPORTS = {
    "kpi_scorecard.md": ("kpi_scorecard.html", "KPI Scorecard",
                         "ICCSD vs. its own board targets and large Iowa peers"),
    "forecast.md": ("forecast.html", "Forecast",
                    "General Fund & solvency, reconciled to PFM's projection"),
    "liquidity.md": ("liquidity.html", "Liquidity",
                     "Month-by-month General Fund cash, with the warrant package"),
    "board_materials_triage.md": ("board_materials_triage.html", "Board Materials",
                                  "Which board documents feed the forecast — and which are noise"),
}
NAV_ITEMS = [
    ("index.html", "Home"),
    ("kpi_scorecard.html", "KPI Scorecard"),
    ("forecast.html", "Forecast"),
    ("liquidity.html", "Liquidity"),
    ("bond_rating_assessment.html", "Bond Rating"),
    ("board_materials_triage.html", "Board Materials"),
    (GH, "GitHub ↗"),
]

# --------------------------------------------------------------------------- #
# Minimal Markdown -> HTML
# --------------------------------------------------------------------------- #
_REPORT_MD = {k: v[0] for k, v in REPORTS.items()}


def inline(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    def _link(m):
        text, url = m.group(1), m.group(2)
        url = _REPORT_MD.get(url, url)            # rewrite report .md links to .html
        return f'<a href="{url}">{text}</a>'
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _link, t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    return t


def _split_row(row: str) -> list[str]:
    row = row.strip().strip("|").replace("\\|", "\x00")
    return [c.strip().replace("\x00", "|") for c in row.split("|")]


def _table(rows: list[str]) -> str:
    header = _split_row(rows[0])
    sep_ok = len(rows) > 1 and set(rows[1].replace("|", "").strip()) <= set("-: ")
    body = rows[2:] if sep_ok else rows[1:]
    h = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead><tbody>"
    for r in body:
        h += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in _split_row(r)) + "</tr>"
    return h + "</tbody></table>"


def _quote(lines: list[str]) -> str:
    parts, cur = [], []
    for ln in lines:
        if ln.strip() == "":
            if cur: parts.append(" ".join(cur)); cur = []
        else:
            cur.append(ln.strip())
    if cur: parts.append(" ".join(cur))
    return "<blockquote>" + "".join(f"<p>{inline(p)}</p>" for p in parts) + "</blockquote>"


def md_to_html(md: str) -> tuple[str, str]:
    """Return (hero_title, body_html). The leading '# Title' becomes the hero."""
    lines = md.split("\n")
    title = ""
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    out, para, i, n = [], [], 0, len(lines)

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para).strip()) + "</p>")
            para.clear()

    while i < n:
        s = lines[i].strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            flush(); lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            flush(); out.append("<hr>"); i += 1; continue
        if s.startswith("|"):
            flush(); tbl = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i].strip()); i += 1
            out.append(_table(tbl)); continue
        if s.startswith(">"):
            flush(); bq = []
            while i < n and lines[i].strip().startswith(">"):
                bq.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append(_quote(bq)); continue
        if re.match(r"^([-*]|\d+\.)\s+", s):
            flush(); items, ordered = [], bool(re.match(r"^\d+\.\s", s))
            while i < n:
                st = lines[i].strip()
                mm = re.match(r"^([-*]|\d+\.)\s+(.*)", st)
                if mm:
                    items.append(inline(mm.group(2))); i += 1
                elif st and lines[i].startswith(" ") and not st.startswith(("|", "#")):
                    if items: items[-1] += " " + inline(st)
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            continue
        para.append(s); i += 1
    flush()
    return title, "\n".join(out)


# --------------------------------------------------------------------------- #
# Page shell
# --------------------------------------------------------------------------- #
def nav(active: str) -> str:
    links = "".join(
        f'<a href="{href}"{" aria-current=page" if href == active else ""}>{label}</a>'
        for href, label in NAV_ITEMS)
    return ('<nav class="topnav"><a class="brand" href="index.html">ICCashForecast</a>'
            f'<div class="links">{links}</div></nav>')


FOOTER = (
    '<footer><p><b>About.</b> ICCashForecast is an <b>unofficial</b> analysis project that '
    'extracts Iowa City Community School District financial data from public records and builds '
    'a transparent General Fund cash forecast. It is <b>not affiliated</b> with ICCSD, Moody&rsquo;s, '
    'S&amp;P, or PFM. Figures are estimates carrying material uncertainty; nothing here is investment '
    f'advice.</p><p class="src">Sources: ICCSD audited ACFRs, Iowa DOM filings, and PFM board '
    f'presentations. Built from the <a href="{GH}">ICCashForecast repository</a>. '
    'Last generated 2026-06-10.</p></footer>')


def page(title: str, body: str, active: str, hero_title: str = "", hero_sub: str = "",
         wrap_content: bool = True) -> str:
    hero = ""
    if hero_title:
        hero = ('<header class="hero"><div class="wrap">'
                '<p class="kicker">ICCashForecast &middot; unofficial analysis</p>'
                f"<h1>{hero_title}</h1>" + (f"<p>{hero_sub}</p>" if hero_sub else "") +
                "</div></header>")
    inner = f'<main class="content">{body}</main>' if wrap_content else body
    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
            '<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{title}</title>\n<link rel=\"stylesheet\" href=\"site.css\">\n</head>\n<body>\n"
            f"{nav(active)}{hero}<div class=\"wrap\">{inner}{FOOTER}</div>\n</body>\n</html>\n")


# --------------------------------------------------------------------------- #
# Landing page
# --------------------------------------------------------------------------- #
LANDING_BODY = f"""
<div class="disclaimer"><b>Unofficial project.</b> ICCashForecast is an independent analysis built
from public records — not affiliated with ICCSD, Moody&rsquo;s, S&amp;P, or PFM, and not investment
advice. All figures are estimates with material uncertainty.</div>

<p>A transparent, reproducible cash forecast for the <b>Iowa City Community School District</b>,
built by extracting figures from the district&rsquo;s own board packets, audited financial reports,
and Iowa state filings. Every number traces back to a public source.</p>

<h2>The headline findings</h2>
<div class="grid">
  <div class="finding"><div class="lab">Spending-authority cushion</div>
    <div class="num n-red">2.31%</div>
    <p>FY2025 Unspent Authorized Budget ratio — <b>last of 15 large Iowa districts</b> (peer median
    ~16%) and below the board&rsquo;s 5&ndash;10% target every year since FY2020.</p>
    <a href="kpi_scorecard.html">KPI scorecard &rarr;</a></div>

  <div class="finding"><div class="lab">General Fund solvency (FY2026, base)</div>
    <div class="num n-red">~0.5%</div>
    <p>On PFM&rsquo;s own projection the GF runs a <b>~$6M deficit</b> and stays <b>below its 5%
    solvency floor through FY2029</b> — a structural operating gap, not just timing.</p>
    <a href="forecast.html">Forecast &rarr;</a></div>

  <div class="finding"><div class="lab">Cash &amp; the warrant treadmill</div>
    <div class="num n-orange">$25M</div>
    <p>Operating cash goes negative in <b>Sept 2026</b>; a $25M revenue anticipation warrant bridges
    it, but a <b>second ~$10M warrant</b> is already planned for FY2027.</p>
    <a href="liquidity.html">Liquidity &rarr;</a></div>

  <div class="finding"><div class="lab">Hypothetical 2028 Moody&rsquo;s GO rating</div>
    <div class="num n-blue">Baa1/Baa2</div>
    <p>Most likely a low-investment-grade GO rating (~72% investment grade overall) — with a ~20%
    chance of <b>no rating at all</b> if audits aren&rsquo;t caught up.</p>
    <a href="bond_rating_assessment.html">Rating assessment &rarr;</a></div>
</div>

<h2>The reports</h2>
<div class="card">
<ul>
  <li><a href="kpi_scorecard.html"><b>Financial-KPI scorecard</b></a> — ICCSD&rsquo;s board-policy
  metrics (solvency, UAB) vs. their targets and the large-Iowa-district peer set.</li>
  <li><a href="forecast.html"><b>General Fund forecast (FY2026&ndash;FY2029)</b></a> — solvency and
  UAB projected on PFM&rsquo;s authoritative cash-flow model, with scenario bands.</li>
  <li><a href="liquidity.html"><b>Monthly liquidity forecast</b></a> — month-end GF cash through
  June 2027, including the $25M warrant and the interfund-loan package.</li>
  <li><a href="bond_rating_assessment.html"><b>Hypothetical 2028 Moody&rsquo;s GO rating</b></a> —
  how a GO rating is built, ICCSD scored factor-by-factor, and a probability distribution.</li>
  <li><a href="board_materials_triage.html"><b>Board-materials triage</b></a> — which of ~520 board
  documents actually feed the forecast.</li>
</ul>
</div>

<h2>How it&rsquo;s built</h2>
<p>An auditable pipeline turns source PDFs into canonical data and forecasts:</p>
<div class="card"><p style="margin:2px 0"><b>Inventory</b> (hash, classify, dedupe ~660 documents)
&nbsp;&rarr;&nbsp; <b>Extractors</b> (quarterly financial reports, monthly actuals &rarr; per-fund
cash, receipts &amp; disbursements) &nbsp;&rarr;&nbsp; <b>Forecast</b> (KPI scorecard, GF solvency &amp;
UAB, monthly liquidity) &nbsp;&rarr;&nbsp; <b>This site</b>. Every step is code in the
<a href="{GH}">repository</a> and re-runnable.</p></div>
"""


def main():
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    (DOCS / "index.html").write_text(
        page("ICCashForecast — Iowa City CSD cash forecast", LANDING_BODY, "index.html",
             hero_title="ICCashForecast",
             hero_sub="A transparent cash forecast for the Iowa City Community School District, "
                      "built from public records."),
        encoding="utf-8")
    print("wrote docs/index.html, docs/.nojekyll")

    for md_name, (html_name, _label, sub) in REPORTS.items():
        src = DOCS / md_name
        if not src.exists():
            print(f"  ! missing {md_name}, skipped"); continue
        title, body = md_to_html(src.read_text(encoding="utf-8"))
        (DOCS / html_name).write_text(
            page(f"{title} — ICCashForecast", body, html_name,
                 hero_title=title, hero_sub=sub),
            encoding="utf-8")
        print(f"  {md_name} -> docs/{html_name}")


if __name__ == "__main__":
    main()
