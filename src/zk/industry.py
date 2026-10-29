"""Industry analysis: market structure / value chain, regulatory timeline, and the F&O curbs split into
direct vs second-order effects, each quantified by re-running the same engine.

Text cells restate cached, sourced facts (source IDs -> data/sources.csv). Second-order magnitudes are NOT sourced:
they are explicit, labelled what-if level shifts so the reader sees the elasticity, not a forecast.
"""
from __future__ import annotations

import pandas as pd

from .data import TICKERS, assumptions, facts, v
from .engine import Scenario, dcf

STRUCTURE = pd.DataFrame([
    dict(layer="Exchange", company="BSE", licence_regulator="Recognised stock exchange + clearing corp (ICCL); SEBI-regulated MII",
         structure="Duopoly with NSE in equity derivatives; since 20-Nov-2024 each exchange may offer weekly expiry on only one benchmark index (BSE: Sensex)",
         revenue_model="Transaction charges (options on premium; options ~95% of txn charges), listing fees, data, StAR MF",
         moat="Liquidity network effect; Sensex weekly-expiry franchise; listing base",
         threats="Regulatory volume curbs, STT hike (1-Apr-2026), RBI prop-funding rules (1-Jul-2026), closing-auction change, NSE pricing response",
         src="SEBI_CIRC_132, MINT_CAS, BS_STT, MC_RBI, BSE_PPT_Q1"),
    dict(layer="Depository", company="CDSL", licence_regulator="Depository under Depositories Act 1996; SEBI-regulated MII",
         structure="Duopoly with NSDL; CDSL 18.59 cr demat accounts (30-Jun-2026), ~80% of accounts; incremental account share down ~420 bp since Mar-26 to 81.4%",
         revenue_model="Annual issuer charges (per folio/ISIN), debit-transaction charges, IPO/corporate actions, KYC/e-voting/data",
         moat="Mandatory dematerialisation; DP and issuer connectivity; annuity-like issuer fees",
         threats="True-to-label uniform pricing; fintech brokers routing new accounts to NSDL; market-cyclical transaction/IPO fees",
         src="CDSL_TR_Q1, SEBI_CIRC_92, CDSL_PPT_Q1"),
    dict(layer="MF RTA", company="CAMS", licence_regulator="SEBI-registered Registrar & Transfer Agent; also KRA, insurance repository",
         structure="Two-player MF RTA market: CAMS 67.2% of MF AAUM (Q1 FY27, ex-FoF basis); industry AAUM INR 83.1 tn; CAMS live-SIP share 63.9%",
         revenue_model="bps of serviced AAUM (asset-based ~74% of revenue) + per-transaction fees + non-MF platforms",
         moat="AMC contracts, investor-record migration cost, 23-year average relationship with top-10 MF clients",
         threats="AMC fee renegotiation under TER->BER (1-Apr-2026); share loss to KFin; platform re-architecture execution",
         src="CAMS_PPT_Q1, CAFE_TER"),
    dict(layer="MF RTA / issuer registry", company="KFINTECH", licence_regulator="SEBI-registered RTA; NPS CRA; international fund admin (Ascent)",
         structure="#2 MF RTA: 33.1% overall AAUM share, 32.8% equity AAUM, 36.7% of monthly SIP inflows; 50.2% of NSE-500 issuers (Q2 FY27)",
         revenue_model="bps of AAUM, issuer folio/corporate-action fees, international/alternates admin",
         moat="Issuer-registry scale; won 254 of last 435 new AMC launches (counted by KFin)",
         threats="Same AMC pricing pressure; acquisition integration (Ascent earn-out); promoter sell-down overhang",
         src="KFIN_PPT_Q2, KFIN_ASCENT, KFIN_SHP"),
]).set_index("company")

REG_TIMELINE = pd.DataFrame([
    dict(date="01-Jul-2024 (eff. 01-Oct-2024)", measure="True-to-label: MII charges uniform for all members, no volume slabs; end-client charge = amount MII receives",
         hits="BSE (txn charges), CDSL (DP/transaction charges): pricing reset, lower realisation", src="SEBI_CIRC_92"),
    dict(date="01-Oct-2024 (eff. 20-Nov-2024 to 01-Apr-2025)", measure="Index-derivative curbs: upfront premium collection, no calendar-spread benefit on expiry day, intraday position-limit monitoring, contract size INR 15-20 lakh, one weekly expiry per exchange, +2% ELM on expiry day",
         hits="BSE directly (options premium turnover); CDSL/brokers second-order via fewer active traders", src="SEBI_CIRC_132"),
    dict(date="07-Jul-2025", measure="SEBI study: ~91% of individual F&O traders lost money in FY25; net losses INR 1,05,603 cr (FY24: 74,812 cr); unique individual traders 61.4 lakh (Q1 FY25) -> 42.7 lakh (Q4 FY25); index-options premium turnover -9% YoY (Dec-24 to May-25)",
         hits="Evidence the curbs bite on participation; supports policy persistence (bear case)", src="SEBI_PR39"),
    dict(date="FY26", measure="Index options contracts traded fell ~52% in FY26; NSE/BSE options volumes down >50%",
         hits="BSE/NSE volumes; CDSL transaction activity", src="SEBI_AR26, FOW_FO"),
    dict(date="01-Apr-2026", measure="Budget-2026 STT increase on F&O; SEBI TER -> BER expense framework for MFs",
         hits="BSE (cost of trading up); CAMS/KFin (AMC economics -> RTA yield pressure)", src="BS_STT, CAFE_TER"),
    dict(date="01-Jul-2026", measure="RBI bank-guarantee / proprietary-funding rules; brokers report F&O volumes -20-25%",
         hits="BSE premium ADTV (Q2 FY27 QTD ~INR 225 bn/day, -24% QoQ per HSIE)", src="MC_RBI, HSIE_BSE"),
]).set_index("date")

SECOND_ORDER_TESTS = {  # (label, overrides) - labelled what-if level shifts, magnitudes NOT sourced
    "BSE": ("cash-market & other txn level -10% (fewer active traders)", {"BSE.cash_other_txn.level_mult": 0.90}),
    "CDSL": ("transaction & KYC/new-account revenue level -10% (fewer active traders/new demats)",
             {"CDSL.transaction.level_mult": 0.90, "CDSL.online_data_kyc.level_mult": 0.90}),
    "CAMS": ("MF asset-based revenue level +5% (household savings redirected from F&O to MFs)", {"CAMS.mf_asset_based.level_mult": 1.05}),
    "KFINTECH": ("domestic MF revenue level +5% (same channel as CAMS)", {"KFINTECH.domestic_mf.level_mult": 1.05}),
}


def fo_impact() -> pd.DataFrame:
    """Direct (derivatives-turnover elasticity) vs second-order exposure per company, all from engine re-runs."""
    rows = []
    for t in TICKERS:
        seg = assumptions()["companies"][t]["segments"]
        base = dcf(t)
        f27 = base["forecast"].loc["FY27E"]
        rev = f27["revenue"]
        direct = sum(f27[f"seg_{s}"] * c["e_d"] for s, c in seg.items()) / rev
        mkt = sum(f27[f"seg_{s}"] * c["e_m"] for s, c in seg.items()) / rev
        d30 = dcf(t, Scenario.named("deriv_only"))
        lab, ov = SECOND_ORDER_TESTS[t]
        so = dcf(t, Scenario(name="second_order", overrides=ov))
        so_plus = dcf(t, Scenario(name="deriv_plus_second", deriv_shock=-0.30, overrides=ov))
        rows.append(dict(ticker=t, deriv_weighted_rev_share_fy27e=direct, market_weighted_rev_share_fy27e=mkt,
                         tp_base=base["target_price"], tp_deriv_minus30=d30["target_price"],
                         direct_tp_change=d30["target_price"] / base["target_price"] - 1,
                         second_order_test=lab, tp_second_order=so["target_price"],
                         second_order_tp_change=so["target_price"] / base["target_price"] - 1,
                         tp_deriv_minus30_plus_second=so_plus["target_price"],
                         combined_tp_change=so_plus["target_price"] / base["target_price"] - 1))
    return pd.DataFrame(rows).set_index("ticker")


def concentration() -> pd.DataFrame:
    """Simple concentration metrics from sourced shares (different bases flagged)."""
    C = facts()["companies"]
    cams = v(C["CAMS"]["kpis"]["mf_aaum_share_pct"])
    M = facts()["market_shares"]
    kf, cd = v(M["kfin_mf_aaum_share_pct"]), v(M["cdsl_demat_share_pct"])
    rows = [dict(market="MF RTA (AAUM share)", leader="CAMS", leader_share_pct=cams, second="KFINTECH", second_share_pct=kf,
                 hhi_two_player=cams ** 2 + kf ** 2,
                 note="CAMS Q1 FY27 ex-FoF vs KFin Q2 FY27 overall - different quarter/basis, sum 100.3% (not additive by construction)",
                 src="CAMS_PPT_Q1, KFIN_PPT_Q2"),
            dict(market="Depository (demat accounts)", leader="CDSL", leader_share_pct=cd, second="NSDL", second_share_pct=100.0 - cd,
                 hhi_two_player=cd ** 2 + (100.0 - cd) ** 2, note="CDSL 'approximately 80%' (call); NSDL = remainder (duopoly)",
                 src="CDSL_TR_Q1")]
    return pd.DataFrame(rows).set_index("market")
