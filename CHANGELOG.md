# Changelog

## 2026-10-29: review round 1 (scorecard /workspace/zeckathon-judge/ps01/scorecard.md)

**P0 fixes**

- Local git repository initialised, with a `.gitignore` and one clean commit. No remote is configured, and nothing has been pushed or transferred.
- Added `outputs/submission_report.pdf`, a 7-page report checked with pdfinfo and a test. It contains the 2-page memo plus appendices A–E. `outputs/IC_memo.pdf` is still exactly 2 pages.
- CAMS TP below CMP: the plan is now an explicit conditional-accumulation plan.
  - Band-touch probabilities at 3, 6 and 12 months come from a driftless log-normal barrier formula and from 5 years of history.
  - Expected ₹ deployed, ADV and days to fill are reported.
  - Fallback: review at month 6, return undeployed capital at month 12, use liquid funds in the meantime, no index proxy.
  - The memo title and §1 now state "₹0 deployed at CMP".
- Ke was revisited with sourced inputs only: the regression-beta CI, the CMP-implied beta, and Damodaran India Jan-2026 industry betas.
  - The base case is unchanged and the reasoning is documented in README and report B3.
  - The caveat is disclosed: the rule was written after the bottom-up TPs were computed.

**P1 fixes**

- Industry section (report Appendix A, app tab) with source IDs in every row:
  - value chain and market structure
  - concentration, with shares moved into `facts.yaml`
  - SEBI timeline backed by cached primary circulars
  - direct vs second-order F&O effects, quantified with the engine; second-order magnitudes are labelled what-ifs
- Requirements: `requirements.txt` has exact pins and `requirements.lock` holds the full freeze, which `run_app.sh` and `make setup` install from. Added `xlrd`.

**P2/P3 fixes**

- `dcf_summary` now has `shares_issued`, `dilutive_increment`, `shares_diluted` and `shares_src`.
  - CAMS dilution comes from the AR Ind AS 33 weighted diluted − basic share counts.
  - KFin dilution comes from the H1 diluted vs basic EPS.
  - The CAMS TP moved from 540 to 539 as a result.
- Days to build the position are computed from ADV.
- The CMP note now says it is a Yahoo intraday print at 15:29 IST, not cross-checked to the NSE bhavcopy.
- New `level_mult` override in the engine, used only for the labelled second-order tests.

**Tests**

- 67 tests in total, up from 43. The new ones are in `tests/test_review_fixes.py` plus one extra app test.
