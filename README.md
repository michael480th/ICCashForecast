# ICCashForecast — ICCSD Public Financial Forecast

An **unofficial, citizen-built** project to create visibility into the cash
position of the **Iowa City Community School District (ICCSD)** using publicly
available board materials, district financial reports, state filings,
spreadsheets, PDFs, and meeting transcripts.

> ⚠️ **This is unofficial and should not be relied on for any decision-making.**
> It is not affiliated with, endorsed by, or verified by ICCSD, its Board, its
> staff, or any vendor named in the documents. Forecasts are estimates, not
> official district financial projections. Please refer to the district directly
> and verify against official materials at
> [iowacityschools.org](https://www.iowacityschools.org) or
> [simbli.eboardsolutions.com](https://simbli.eboardsolutions.com).

---

## What this project does

The system lets a user add public source files to this repository, rerun a
data pipeline, and publish an updated static HTML site showing:

- Latest known cash and investment balances by fund
- Monthly projected cash balances by fund
- Base, conservative, and stress-case scenarios
- Risk status per fund: **Good**, **At Risk**, or **Red Flag**
- Source documents behind each number
- Assumptions used in the forecast
- Data-quality warnings and unresolved questions

It is designed as a **durable data pipeline**, not a disposable prototype. Every
extracted number is traceable to a source document, page, sheet, or manual entry.

---

## Pipeline overview

```text
Raw source documents
  ↓  Document inventory  (hash, dedupe, classify)
  ↓  Extraction layer    (PDF tables/text, Excel, transcripts)
  ↓  Raw extracted tables/text
  ↓  Normalization       (canonical funds, dates, numbers, source links)
  ↓  Validation          (totals, duplicates, gaps, staleness)
  ↓  Forecast model       (per fund / month / scenario)
  ↓  Risk scoring        (Good / At Risk / Red Flag)
  ↓  Static HTML dashboard (docs/, published via GitHub Pages)
```

The forecast model never reads directly from raw PDFs or spreadsheets — it only
consumes the normalized canonical tables under `data/normalized/`.

---

## Repository layout

```text
data/
  raw/          Source documents, organized by type and date (input)
    board_packets/        Board meeting materials, by meeting date
    district_reports/     ICCSD's own reports — incl. audits/ (FY20–23 ACFRs)
    state_reports/        Iowa state filings — incl. dom/ (statewide DOM/DE workbooks)
    peer_districts/       Other districts' audits (benchmark context, not forecast input)
    transcripts/  manual_uploads/
  extracted/    Raw extracted tables/text + document_inventory.csv
  normalized/   Canonical financial tables (the forecast's only input)
  manual/       Manual overrides + corrections log
  forecast/     Forecast output, risk scores, scenario comparison
scripts/
  inventory/ extract/ extractors/ normalize/ validate/ forecast/ site/
site/
  templates/ assets/    Static-site source assets
docs/           Generated static site (GitHub Pages publish dir)
tests/          Fixtures + unit tests
.github/workflows/       CI build + publish (added in a later phase)
```

See **[docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md)** for the schema of every
table and **[docs/NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md)** for file and
folder naming rules.

---

## Project status

**Phase 1 — Inventory System (current).** The repository structure, data
dictionary, naming conventions, and canonical `funds.csv` are in place (Phase 0),
and the document inventory system is implemented: it hashes every file in
`data/raw/`, classifies it, builds `document_inventory.csv`, and flags duplicates
and provenance gaps. See [scripts/inventory/](scripts/inventory/README.md).

An initial corpus has been imported from the companion
[ICCSDAdvocacy](https://github.com/michael480th/ICCSDAdvocacy) repository
(**137 documents**): the Iowa City CSD audited ACFRs (FY2020–FY2023), the Iowa
DOM/DE statewide workbooks (spending authority, enrollment, valuations, levies,
at-risk), pre-extracted ICCSD data (raw provenance), and 84 peer-district audits
for benchmark context. Each imported area carries a `PROVENANCE.md`. **Note:**
this corpus is annual baselines and revenue drivers — the *monthly* board cash
reports the forecast ultimately runs on still need to be added from board packets.

The board-packet corpus (14 meetings, Jan–Jun 2026) has been triaged by financial
relevance: of ~520 documents, ~84 feed the forecast and the rest are governance
noise (contracts, DPAs, policies). The extraction target list — gold mines grouped
by the table each feeds — is in
[docs/board_materials_triage.md](docs/board_materials_triage.md), and those
classifications are applied via `data/manual/document_classification_manual.csv`.

Roadmap (see the full project plan):

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Corpus setup: structure, README, data dictionary, funds.csv | ✅ done |
| 1 | Inventory system: hashing, dedupe, classification | ✅ current |
| 2 | First extractor: quarterly financial report → cash/actuals | ⏳ planned |
| 3 | First forecast: General Fund, 3 scenarios, risk scoring | ⏳ planned |
| 4 | Static site: dashboard, fund/source/assumptions/downloads | ⏳ planned |
| 5 | GitHub automation: Actions build + Pages publish | ⏳ planned |
| 6 | Additional inputs: AP, interfund loans, debt service, events | ⏳ planned |
| 7 | More funds: SAVE, PPEL, Management, Debt, Nutrition, Activity | ⏳ planned |
| 8 | Advanced: OCR, transcript NER, change detection, backtesting | ⏳ planned |

---

## Adding source documents

1. Place files under `data/raw/` following the layout in
   [docs/NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md), e.g.
   `data/raw/board_packets/YYYY-MM-DD/financial_report.pdf`.
2. Record the source URL in a `source_urls.md` next to the files.
3. Rebuild the inventory to register and classify the new files:

   ```bash
   python scripts/inventory/build_document_inventory.py
   python scripts/inventory/detect_duplicates.py
   ```

   Later phases will extend this into the full extract → normalize → forecast →
   site run (locally or via GitHub Actions).

Manual data entry and corrections go under `data/manual/` and must always cite a
source file and page. Manual overrides never silently replace extracted values;
the dashboard discloses when a value was manually entered or corrected.

---

## License

See [LICENSE](LICENSE). Source documents referenced by this project remain the
property of their respective owners and are public records of ICCSD.
