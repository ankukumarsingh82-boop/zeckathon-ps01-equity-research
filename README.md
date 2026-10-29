# Zeckathon PS-01: BSE vs CDSL vs CAMS vs KFin Technologies

This project is a reproducible equity-research model and a local app. It produces:

- a comparable DCF for all four companies, with P/E and EV/EBITDA as cross-checks
- bull, base and bear scenarios, plus the two brief-mandated stresses on their own
- sensitivity grids
- an integrated three-statement model for the winner
- moat, financial-quality and governance tables
- a ₹500 cr deployment plan
- a two-page IC memo (`outputs/IC_memo.pdf`)
- a full submission report, 7 pages (`outputs/submission_report.pdf`): the memo plus appendices A (industry and SEBI F&O curbs), B (valuation bridge, relative valuation and Ke cross-check), C (diligence and three-statement model), D (scenarios and sensitivities) and E (deployment timeline, liquidity and sources)

The price and valuation date is **29-Oct-2026**. CMP is the last Yahoo Finance intraday print, a daily bar stamped 15:29 IST on 29-Oct-2026 (CAMS ₹696.95). It is **not** cross-checked against the NSE bhavcopy official close. All money figures are INR crore unless they are stated per share.

## One-command run (offline, no API keys)

```bash
./run_app.sh            # creates .venv if needed, builds outputs if missing, opens http://localhost:8501
```

Other commands (see the `Makefile`):

```bash
make setup              # python3 -m venv .venv && pip install -r requirements.lock (exact pins)
make all                # .venv/bin/python run_all.py   -> outputs/*.csv, model_outputs.xlsx, summary.json, IC_memo.pdf, submission_report.pdf
make test               # pytest (67 tests)
make app                # streamlit run app.py
```

Requirements and network use:

- Python 3.13 (tested on 3.13.5).
- `requirements.txt` pins the direct dependencies exactly, and `requirements.lock` is the full `pip freeze` of the tested environment. `run_app.sh` and `make setup` install from the lock.
- Optional: `pdftotext` (poppler-utils) for the in-app memo text preview. The PDF download works without it.
- Nothing is deployed, and no LLM key or other key is needed.
- Every input is read from cached files in `data/raw`, `data/inputs` and `config`.

### Optional data refresh

Data refresh is optional and needs a Firecrawl key:

```bash
export FIRECRAWL_API_KEY=...       # optional; without it the refresh is a no-op
make refresh                       # fetches Screener pages (via Firecrawl) + Yahoo prices into data/refresh/<date>/
PYTHONPATH=src .venv/bin/python -m zk.refresh --apply   # copies them into data/raw and re-pins CMP + valuation_date
```

The refresh only fetches Screener pages and prices. Facts transcribed from filings (annual reports, investor decks) are never overwritten automatically. After a new results release, update `data/inputs/facts.yaml` by hand, citing the source.

## The local app (`app.py`)

The sidebar controls:

- G-sec, the default spread, ERP, terminal g and a Ke adjustment
- derivatives and equity-market shocks, a growth delta and a g delta, starting from any preset
- scenario weights

The app recomputes the model live and has these tabs:

1. scoreboard and winner
2. per-company DCF and equity bridge
3. scenario table
4. sensitivities: WACC × g, ERP × β, driver × market, tornado
5. three-statement model with balance checks
6. diligence
7. ₹500 cr plan, with deployment odds, expected deployment and liquidity
8. IC memo and full report downloads, plus regeneration
9. sources
10. industry and SEBI F&O curbs (direct vs second-order)
11. Ke cross-check (beta CI, Damodaran India industry betas)

## Layout

| Path | What |
|---|---|
| `data/raw/` | Cached source documents: Screener HTML and schedules JSON, annual-report and investor-presentation PDFs and text, Yahoo price JSON, Damodaran CRP page and India beta xls, Yahoo 5y daily bars, SEBI circulars 2024/92 and 2024/132 |
| `data/sources.csv` | Source ID, URL, local file and access date for every source |
| `data/inputs/facts.yaml` | Hand-transcribed facts. Each one carries `value`, `src` (an ID in sources.csv) and `ref` (the page, note or line) |
| `data/processed/screener_long.csv` | Parsed Screener tables, with source_url and access_date on every row |
| `config/assumptions.yaml` | Every judgemental assumption, each with a `why` |
| `src/zk/engine.py` | Segment-driver forecast, FCFF, three-stage DCF, equity bridge, 12-month TP, multiples |
| `src/zk/scenarios.py` | Scenarios, implied Ke and winner selection |
| `src/zk/three_statement.py` | CAMS integrated P&L, balance sheet and cash flow |
| `src/zk/sensitivity.py` | Grids and tornado; every cell is a full re-run |
| `src/zk/diligence.py` | Earnings quality, moat and governance |
| `src/zk/allocation.py` | ₹500 cr tranches. Entry prices are model outputs |
| `src/zk/memo.py` | Two-page IC memo |
| `src/zk/report.py` | Full submission report (memo + appendices A-E, ≤ 8 pages) |
| `src/zk/deployment.py` | Band-touch odds (model and history), ADV, days to fill |
| `src/zk/ke_crosscheck.py` | Beta CI, CMP-implied beta, Damodaran India bottom-up betas |
| `src/zk/industry.py` | Value-chain table, concentration, SEBI timeline, F&O direct vs second-order |
| `CHANGELOG.md`, `READY_FOR_REVIEW.md` | Review-round changes and status |
| `src/zk/refresh.py` | Optional Firecrawl refresh |
| `tests/` | Model-integrity, traceability and app tests |

## Method, in brief

**Revenue.** Revenue is built per segment from the latest reported quarter or quarters:

- BSE: Q1 FY27
- CDSL: Q1 FY27
- CAMS: Q1 FY27
- KFin: H1 FY27

Each segment has an explicit elasticity to derivatives turnover (`e_d`) and to the equity-market level (`e_m`). Shocks are applied from Q3 FY27 as persistent level shifts. BSE's derivatives revenue is premium ADTV × days × realisation, where realisation is calibrated on Q1 FY27 and Q2 uses the HSIE QTD premium ADTV.

**Costs.**

- Variable costs are a share of revenue, set from the latest quarter.
- Fixed costs come from latest-quarter opex less the variable part and grow at 10% a year.
- D&A follows the FY26 percentage of revenue.
- Capex is the FY25–26 average percentage of revenue.
- ΔNWC is a percentage of incremental revenue.

**Cost of equity.**

- rf = 10-year G-sec of 7.40%, less the India sovereign CDS of 0.66%, giving 6.74%.
- ERP = 5.23% (Damodaran, Jan 2026, CDS-based).
- β = Blume-adjusted 3-year weekly beta against the Nifty 50.
- WACC equals Ke because all four companies hold net cash.

**DCF stages.** FY27E–FY31E are explicit. FY32–FY41 fade linearly to g = 6.5%, followed by a Gordon terminal value. Cash flows are timed from each company's balance-sheet date to the valuation date.

**Equity bridge.** Equity value is:

- EV
- plus **owned** cash and investments (clearing, SGF, trust and earmarked funds are excluded)
- less operating liabilities funded by that cash
- less leases and debt-like items
- plus associates (BSE's 15% CDSL stake at market)
- less NCI
- less dividends paid since the balance-sheet date.

**12-month TP.** TP = value today × (1 + Ke) − next-12-month DPS. P/E and EV/EBITDA are cross-checks only.

**Winner selection.** The winner has the highest probability-weighted (25/50/25) 12-month total return less 0.5 × the bear-case loss against CMP.

## Results (from `outputs/summary.json`)

| | CMP | TP base | vs CMP | TP bear | TP bull | Implied Ke | CAPM Ke |
|---|---|---|---|---|---|---|---|
| **CAMS (winner)** | 696.95 | 539 | −23% | 340 | 705 | 11.2% | 13.2% |
| KFin | 859.8 | 560 | −35% | 306 | 771 | 10.9% | 13.6% |
| BSE | 3,502 | 1,503 | −57% | 1,046 | 1,869 | 9.1% | 13.9% |
| CDSL | 1,282 | 358 | −72% | 237 | 456 | 8.5% | 15.2% |

**At CMP none of the four clears its CAPM cost of equity.** CAMS ranks first on every selection metric and has no direct derivatives exposure. Its CMP implies a Ke about 2 percentage points below our CAPM Ke. The CAMS TP fell from 540 to 539 because diluted shares now include the Ind AS 33 ESOP increment (24.9305 cr).

### ₹500 cr plan: conditional accumulation, ₹0 deployed at CMP

| Tranche | Amount | Buy at or below | Fall vs CMP | P(touch) 6m model / hist | P(touch) 12m model / hist | Sessions to fill at 20% of ADV |
|---|---|---|---|---|---|---|
| T1 | ₹100 cr | ₹637 | −9% | 67% / 60% | 76% / 70% | 4.6 |
| T2 | ₹150 cr | ₹564 | −19% | 32% / 23% | 48% / 34% | 6.9 |
| T3 | ₹250 cr | ₹490 | −30% | 10% / 7% | 24% / 9% | 11.5 |

- **Expected deployment.** About ₹139 cr by 6 months and ₹208 cr by 12 months under the model (₹111 cr and ₹145 cr on history).
  - The model is a driftless log-normal barrier probability, with σ = 30.0% from 252 sessions of CAMS.NS.
  - History is the share of all 5-year daily start dates that touched the band. The windows overlap, so they are not independent.
- **Liquidity.** ADV is ₹109 cr (NSE + BSE, 60 sessions). The whole ticket fills in about 23 sessions at 20% participation and is 2.9% of market cap.
- **Timeline and fallback.**
  - Month 0–1: no buying above T1. Wait for Q2 FY27 results.
  - Months 1–6: tranches fill only when their band trades.
  - Month 6 (after Q4 FY27): re-run the model on actuals. Bands move only through the model.
  - Month 12: capital still undeployed goes back to the fund. It is not forced into the stock and not parked in an index proxy, because every listed peer trades above model value. Until then it sits in overnight or liquid funds.
- **Why not a starter buy at CMP?** The model's base 12-month total return at CMP is negative, so buying now would contradict our own valuation.

## Cost-of-equity decision (reviewed, not tuned)

The reviewer asked us to revisit Ke only with sourced justification. Here is what we did (`src/zk/ke_crosscheck.py`, report Appendix B3):

1. **Precision of the regression beta.**
   - The 156-week regression gives each company an OLS standard error. For CAMS the 95% CI on the Blume beta is 0.99–1.49, which puts the TP between ₹456 and ₹663.
   - The beta that CAMS's CMP implies is 0.86, outside that CI.
2. **Bottom-up industry betas.** These come from Damodaran's India dataset (Jan-2026, `data/raw/damodaran_betaIndia.xls`, "Unlevered beta corrected for cash").
   - The dataset has no exchange, depository or RTA industry. The five candidate industries range from 0.49 to 1.02, so picking one would amount to picking the answer.
   - Only "Information Services" (1.02) falls inside CAMS's CI. It gives a TP of ₹646, still below CMP. The other buckets would give ₹877–1,274, but their betas sit outside the measured CI.
3. **ERP alternatives.** The rating-based ERP of 7.08%, paired with its matching rf, is already in the ERP × β grid.

**Decision:** the base case keeps the regression beta. Honest caveat: we wrote this decision rule after computing the bottom-up TPs, so judge it on its logic.

## Industry analysis (report Appendix A, `src/zk/industry.py`)

- **Value chain.** Exchange (BSE), depository (CDSL), MF RTA (CAMS, KFin). The table gives licence, structure, revenue model, moat and threats, with a source ID in every row.
- **Concentration.** RTA HHI is 5,611 (CAMS 67.2% vs KFin 33.1%, on different quarters and bases). Depository HHI is 6,800 (CDSL "approximately 80%").
- **Regulatory timeline.** SEBI CIR/2024/92 (true-to-label), CIR/2024/132 (six index-derivative measures), the SEBI FY25 F&O study, the FY26 −52% in index options, Budget-2026 STT and TER→BER, and the Jul-2026 RBI funding rules. Primary circulars are cached in `data/raw/`.
- **Direct vs second-order effects, from engine re-runs.**
  - Direct effect of derivatives turnover −30%: BSE −10.9%, CDSL −0.6%, CAMS and KFin 0%.
  - Second-order effects are labelled what-ifs whose **magnitudes are not sourced**: BSE cash −10%, CDSL transaction/KYC −10%, RTA MF revenue +5%. They are not part of any scenario.

## Integrity checks (pytest)

The tests check that:

- the balance sheet balances in every year and scenario
- the cash-flow closing cash equals balance-sheet treasury
- three-statement FCFF equals DCF-engine FCFF
- retained earnings roll forward correctly
- the opening balance sheet equals the audited Mar-26 totals: total assets ₹1,810.38 cr, liabilities ₹489.51 cr, equity ₹1,320.91 cr
- every fact's `src` exists in sources.csv, with a URL and access date
- Screener FY26 revenue matches the annual report within 1%
- segment sums tie to reported revenue
- bear < base < bull
- shocks never raise value
- the derivatives shock hits BSE hardest and CAMS not at all
- the WACC × g grid is monotonic
- the TP formula holds
- EV decomposes into its parts
- the Streamlit app runs offline without exceptions and has the Industry and Ke tabs
- review-round logic (`tests/test_review_fixes.py`):
  - the touch probability is bounded, monotone, equal to the reflection formula and matched by Monte Carlo
  - empirical touch frequency is correct on a synthetic series
  - days to fill = amount / (participation × ADV), and ADV is recomputed from the raw bars
  - diluted = issued + increment, and the CAMS increment matches the annual report
  - the Damodaran value is read correctly, and TP falls monotonically in β
  - the base case still uses the regression β
  - the memo's Ke claims hold
  - every industry source ID exists
  - `level_mult` is monotone
  - only BSE has a material direct F&O effect
  - the memo is exactly 2 pages and the report ≤ 8
  - requirements are exactly pinned
  - the price note is honest

Note: `test_selection_winner_is_deterministic` asserts CAMS. It is a regression lock on the current cached inputs and should be updated deliberately if those inputs change.

## Assumptions (labelled; full list with reasons in `config/assumptions.yaml`)

- Segment elasticities `e_d` and `e_m`, and FY28–31 segment growth rates
- Scenario definitions:
  - bear: derivatives −30% and market −20%, growth −3pp, g −1pp
  - bull: +15%, +10%, +2pp, +0.5pp
  - weights 25/50/25
- Terminal g 6.5%, a 10-year fade, fixed-cost growth 10%, cash yield 7% (used for EPS only)
- BSE H2 FY27 premium ADTV equal to the Q2 QTD level
- Payout ratios: BSE 40%, CDSL 55%, CAMS 70%, KFin 60%
- Leases held flat in the three-statement model
- Dividend payment dates assumed to fall before the price date

## Data gaps / unresolved items (marked, not silently estimated)

1. **Q2 FY27 results for BSE, CDSL and CAMS are not yet released.** Their run-rates use Q1. BSE Q2 premium ADTV is broker data (HSIE, secondary).
2. **CAMS FY26 segment split is approximated** from the average of the Q1 FY26 and Q4 FY26 revenue mix. It is used only for context; the forecast is driven by Q1 FY27 actuals.
3. **KFin variable-cost share is assumed at 10%** of revenue; it is not disclosed.
4. **KFin's ₹676 cr consolidated non-current financial liability** is inferred to be the Ascent 49% earn-out. Its composition is **unverified**. It is deducted as debt-like.
5. **CDSL's other current financial liabilities (₹237 cr)** are deducted in full as a conservative choice; their composition is not verified.
6. **BSE share count:** three figures exist (40.61, 40.79 and 41.198 cr). The annual-report weighted figure, 41.198 cr, is used and is conservative.
7. **KFin FY26 annual report:** only a cover letter was retrieved. The Sep-26 balance sheet comes from the Q2 FY27 presentation instead.
8. **ADV now checked** (Yahoo daily NSE + BSE volumes, not exchange bhavcopies). Block or bulk-deal availability has not been checked.
9. **Second-order F&O effects are quantified only as labelled what-ifs.** No source measures how much F&O money moves into MFs.
10. **The SEBI FY25 F&O study PDF (SEBI_PR39) could not be downloaded** because sebi.gov.in timed out. Its figures are cited from the SEBI URL and Indian Express / Business Standard reports.
11. **CMP not checked against the NSE bhavcopy** (see the price note above).
12. **The bottom-up industry mapping is a judgement call.** The table shows every candidate.
