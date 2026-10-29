"""Financial quality (PAT vs CFO vs FCF), moat and governance evidence tables."""
from __future__ import annotations

import pandas as pd

from .data import TICKERS, screener_table

YRS = ["Mar 2024", "Mar 2025", "Mar 2026"]


def earnings_quality() -> pd.DataFrame:
    rows = []
    for t in TICKERS:
        cf = screener_table(t, "cash-flow"); pl = screener_table(t, "profit-loss"); r = screener_table(t, "ratios")
        pat = pl.loc["Net Profit", YRS].sum(); cfo = cf.loc["Cash from Operating Activity", YRS].sum()
        fcf = cf.loc["Free Cash Flow", YRS].sum()
        rows.append(dict(ticker=t, pat_fy24_26=pat, cfo_fy24_26=cfo, fcf_fy24_26=fcf, cfo_to_pat=cfo / pat, fcf_to_pat=fcf / pat,
                         cfo_to_pat_fy24=cf.loc["Cash from Operating Activity", "Mar 2024"] / pl.loc["Net Profit", "Mar 2024"],
                         cfo_to_pat_fy25=cf.loc["Cash from Operating Activity", "Mar 2025"] / pl.loc["Net Profit", "Mar 2025"],
                         cfo_to_pat_fy26=cf.loc["Cash from Operating Activity", "Mar 2026"] / pl.loc["Net Profit", "Mar 2026"],
                         debtor_days_fy26=r.loc["Debtor Days", "Mar 2026"], debtor_days_fy24=r.loc["Debtor Days", "Mar 2024"],
                         roce_fy24=r.loc["ROCE %", "Mar 2024"], roce_fy26=r.loc["ROCE %", "Mar 2026"]))
    return pd.DataFrame(rows).set_index("ticker")


MOAT = pd.DataFrame([
    dict(ticker="BSE", moat="Exchange duopoly (with NSE); network effects in liquidity; listing/cash franchise",
         fragility="~65% of FY26 revenue = equity derivatives (facts.yaml segments); SEBI F&O curbs, STT hike (BS_STT), RBI prop-funding rules (MC_RBI) and CAS directly hit volume/realisation",
         rating="Strong but regulator-dependent", src="BSE_AR26, BSE_PPT_Q1, SEBI_AR26, MINT_CAS"),
    dict(ticker="CDSL", moat="Depository duopoly with NSDL; annual issuer charges are annuity-like",
         fragility="Transaction/IPO/KYC revenue is market-cyclical; FY26 PAT fell YoY (455 vs 526, SCR_CDSL)",
         rating="Strong, cyclical earnings", src="CDSL_PPT_Q1, SCR_CDSL"),
    dict(ticker="CAMS", moat="RTA duopoly with KFin; 67.2% MF AAUM share (CAMS_PPT_Q1); multi-year AMC contracts, high switching cost (data migration, investor servicing)",
         fragility="Asset-based fees tied to AAUM (54.3% equity) and AMC pricing pressure (TER->BER, CAFE_TER); zero direct F&O exposure",
         rating="Strongest; least regulatory-volume exposure", src="CAMS_PPT_Q1, CAMS_AR26, CAFE_TER"),
    dict(ticker="KFINTECH", moat="#2 MF RTA; issuer registry; growing international (Ascent) and alternates",
         fragility="Market-share challenger; acquisitions add goodwill (INR 1,336 cr Sep-26, KFIN_PPT_Q2) and an earn-out (KFIN_ASCENT); debtor days 76 (FY26)",
         rating="Good, execution/integration risk", src="KFIN_PPT_Q2, KFIN_ASCENT, SCR_KFIN"),
]).set_index("ticker")

GOVERNANCE = pd.DataFrame([
    dict(ticker="BSE", item="MD&CEO Sundararaman Ramamurthy retires 15-Jun-2027 (age limit); successor search open, applications due 19-Nov-2026",
         flag="AMBER - key-man/strategy continuity during regulatory transition", src="BSE_CEO"),
    dict(ticker="BSE", item="Reported operating cash flow includes movements in clearing/settlement funds (CFO/PAT 3.4x FY24; 1.25x FY26)",
         flag="AMBER - use owned cash only (done in bridge)", src="SCR_BSE, BSE_AR26"),
    dict(ticker="CDSL", item="BSE holds 15% (promoter); MII governance under SEBI; FY26 EPS decline",
         flag="GREEN/AMBER", src="SCR_CDSL, BSE_AR26"),
    dict(ticker="CAMS", item="No promoter; related-party transactions limited to KMP remuneration at arm's length (Note 30); auditor S.R. Batliboi",
         flag="GREEN", src="CAMS_AR26"),
    dict(ticker="CAMS", item="Intangibles under development up from INR 38 cr to INR 88 cr; capital commitments INR 123 cr mostly cloud contracts for new RTA platform",
         flag="AMBER - capitalisation policy and platform migration risk", src="CAMS_AR26"),
    dict(ticker="KFINTECH", item="Promoter General Atlantic sold 8.75% at INR925 (Aug-2026); promoter holding 14.06% (Sep-26) - overhang",
         flag="AMBER - supply overhang", src="KFIN_SHP"),
    dict(ticker="KFINTECH", item="INR 676 cr consolidated non-current financial liability inferred as Ascent 49% earn-out (composition UNVERIFIED); deducted as debt-like",
         flag="AMBER - UNVERIFIED", src="KFIN_PPT_Q2, KFIN_ASCENT"),
])
