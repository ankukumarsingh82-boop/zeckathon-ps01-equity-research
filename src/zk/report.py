"""Submission report (<= 8 A4 pages): the 2-page IC memo followed by appendices A-E, all generated from model outputs."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Table, TableStyle

from . import OUT, ROOT
from .memo import B, H, S, T, doc_for, memo_story

C = Paragraph  # alias for wrapped cells


def _ptable(df: pd.DataFrame, widths, fs=6.2, header=None, fmt=None, index_label=""):
    """DataFrame -> wrapped table. fmt: dict col -> format string or callable."""
    fmt = fmt or {}
    cs = S.clone("cell", fontSize=fs, leading=fs + 1.3, textColor=colors.black)
    hs = cs.clone("hcell", fontName="Helvetica-Bold")
    cols = list(df.columns)
    rows = [[C(index_label, hs)] + [C(str(h), hs) for h in (header or cols)]]
    for idx, r in df.iterrows():
        cells = [C(str(idx), cs)]
        for c in cols:
            x = r[c]
            f = fmt.get(c)
            if callable(f):
                s = f(x)
            elif f and isinstance(x, (int, float)) and pd.notna(x):
                s = format(x, f)
            else:
                s = str(x)
            cells.append(C(s, cs))
        rows.append(cells)
    t = Table(rows, colWidths=widths, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe8f2")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 0.8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8), ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


def _grid(df: pd.DataFrame, label: str, fs=6.2, cw=15*mm, f="{:.0f}", hl=None):
    cs = S.clone("g", fontSize=fs, leading=fs + 1.3, textColor=colors.black)
    rows = [[C(label, cs)] + [C(str(c), cs) for c in df.columns]]
    for i, r in df.iterrows():
        rows.append([C(str(round(i, 3)) if isinstance(i, float) else str(i), cs)] + [C(f.format(x), cs) for x in r])
    t = Table(rows, colWidths=[28*mm] + [cw]*len(df.columns), hAlign="LEFT")
    st = [("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe8f2")),
          ("TOPPADDING", (0, 0), (-1, -1), 0.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6)]
    if hl is not None:
        st.append(("BACKGROUND", (0, hl), (-1, hl), colors.HexColor("#fff4cc")))
    t.setStyle(TableStyle(st))
    return t


pct = lambda x: f"{x:+.1%}"
pct0 = lambda x: f"{x:.0%}"


def appendix_story(res: dict) -> list:
    tabs, p, dep = res["tabs"], res["plan"], res["deploy"]
    w = p["winner"]
    st = [PageBreak(), Paragraph("Appendix A - Industry: India's capital-market 'toll collectors'", T)]
    st.append(Paragraph("A1. Value chain, licences and market structure. Every cell restates a cached source (IDs -> data/sources.csv; local copies in data/raw/).", H))
    s = tabs["industry_structure"][["layer", "licence_regulator", "structure", "revenue_model", "moat", "threats", "src"]]
    st.append(_ptable(s, [13*mm, 13*mm, 25*mm, 38*mm, 30*mm, 24*mm, 25*mm, 18*mm],
                      header=["Layer", "Licence / regulator", "Structure & share", "Revenue model", "Moat / switching cost", "Threats", "Sources"], fs=5.9))
    st.append(Paragraph("A2. Concentration (two-player markets).", H))
    c = tabs["concentration"]
    st.append(_ptable(c[["leader", "leader_share_pct", "second", "second_share_pct", "hhi_two_player", "note", "src"]],
                      [32*mm, 13*mm, 12*mm, 14*mm, 12*mm, 14*mm, 60*mm, 24*mm],
                      header=["Leader", "Share %", "#2", "Share %", "HHI", "Basis note", "Sources"], fmt={"hhi_two_player": ".0f", "leader_share_pct": ".1f", "second_share_pct": ".1f"}))
    st.append(Paragraph("Reading: every layer is a regulated duopoly. Pricing power is capped by SEBI (true-to-label uniform MII charges; TER->BER for AMCs), "
                        "so moats protect volume share more than price. The exchange's revenue is a toll on trading activity; the depository's is part annuity "
                        "(issuer fees) and part activity; the RTAs' is a toll on assets (bps of AAUM), which is why the F&O curbs reach them only indirectly.", B))
    st.append(Paragraph("A3. Regulatory timeline: SEBI F&O curbs, fee rationalisation and related shocks", H))
    st.append(_ptable(tabs["regulatory_timeline"], [30*mm, 92*mm, 50*mm, 14*mm], header=["Measure", "Who it hits", "Sources"], index_label="Date"))
    st.append(Paragraph("A4. F&O curbs: direct vs second-order effects, quantified with the same engine (12-month TP, INR)", H))
    f = tabs["fo_direct_vs_second_order"]
    st.append(_ptable(f, [14*mm, 14*mm, 14*mm, 13*mm, 14*mm, 13*mm, 40*mm, 14*mm, 13*mm, 15*mm, 13*mm],
                      header=["Deriv.-elastic rev share FY27E", "Market-elastic rev share", "TP base", "TP deriv -30%", "Direct TP chg",
                              "2nd-order what-if (labelled, magnitude NOT sourced)", "TP 2nd-order", "2nd-order chg", "TP deriv -30% + 2nd", "Combined chg"],
                      fmt={"deriv_weighted_rev_share_fy27e": pct0, "market_weighted_rev_share_fy27e": pct0, "tp_base": ".0f", "tp_deriv_minus30": ".0f",
                           "direct_tp_change": pct, "tp_second_order": ".0f", "second_order_tp_change": pct, "tp_deriv_minus30_plus_second": ".0f",
                           "combined_tp_change": pct}, fs=5.8))
    st.append(Paragraph(
        "<b>Direct</b> (revenue that moves one-for-one with derivatives turnover): only BSE - equity derivatives were ~65% of FY26 revenue and options are ~95% of "
        "transaction charges (BSE_PPT_Q1, MINT_CAS); the clearing float also scales with margins. A 30% fall costs BSE ~11% of TP even after its variable "
        "regulatory/SGF costs fall with revenue. <b>Second-order</b>: CDSL loses debit transactions and new-account/KYC fees as active traders fall (unique F&O "
        "traders fell 61.4 -> 42.7 lakh across FY25, SEBI_PR39) but its issuer annuity is untouched; CAMS and KFin have no derivatives revenue - the channel is household "
        "savings: if money that left F&O goes to MFs (CAMS: equity net sales +43% YoY, SIP collections +20.7% YoY in Q1 FY27, CAMS_PPT_Q1), RTA AAUM rises. "
        "We found no source that measures that switch, so the +5% is a labelled what-if, not in any scenario. Elasticities e_d / e_m per segment are in config/assumptions.yaml.", B))

    st.append(PageBreak())
    st.append(Paragraph("Appendix B - Valuation detail (identical engine for all four)", T))
    st.append(Paragraph("B1. EV -> equity -> 12-month TP bridge (INR cr unless per share). Diluted shares = period-end issued + Ind AS 33 dilutive ESOP increment.", H))
    d = tabs["dcf_summary"].T.loc[["beta", "ke", "g", "pv_explicit", "pv_fade", "pv_terminal", "tv_share", "ev", "net_cash", "associates", "nci",
                                   "dividends_since_bs", "equity", "shares_issued", "dilutive_increment", "shares_diluted", "value_ps", "dps12",
                                   "target_price", "cmp", "upside"]]
    fm = {"beta": "{:.2f}", "ke": "{:.2%}", "g": "{:.2%}", "tv_share": "{:.0%}", "upside": "{:+.1%}", "shares_issued": "{:.4f}",
          "dilutive_increment": "{:.4f}", "shares_diluted": "{:.4f}", "value_ps": "{:.1f}", "dps12": "{:.1f}", "target_price": "{:.1f}", "cmp": "{:.2f}"}
    cs = S.clone("c2", fontSize=6.2, leading=7.4, textColor=colors.black)
    rows = [[C("", cs)] + [C(c, cs) for c in d.columns]]
    for i, r in d.iterrows():
        rows.append([C(i, cs)] + [C(fm.get(i, "{:,.0f}").format(float(x)), cs) for x in r])
    t = Table(rows, colWidths=[34*mm] + [22*mm]*4, hAlign="LEFT")
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe8f2")),
                           ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                           ("BACKGROUND", (0, 19), (-1, 19), colors.HexColor("#fff4cc"))]))
    st.append(t)
    st.append(Paragraph("equity = EV + net cash + associates - NCI - dividends paid since the balance-sheet date; TP = value/share x (1 + Ke) - DPS over the next 12 months. "
                        "An independent reviewer recomputation reproduced all four TPs exactly (pre-dilution fix). Share-count sources: "
                        + "; ".join(f"{k}: {v}" for k, v in tabs["dcf_summary"]["shares_src"].items()), S))
    st.append(Paragraph("B2. Relative valuation at CMP (cross-check, not the TP driver)", H))
    rel = tabs["relative"][["pe_ttm", "pe_fy27e", "pe_fy28e", "ev_ebitda_fy26", "ev_ebitda_fy27e", "ev_ebitda_fy28e", "rev_cagr_fy24_26_screener",
                            "eps_cagr_fy27_29", "roce_fy26_pct", "ebitda_margin_fy27e", "peg_fy28"]]
    st.append(_ptable(rel, [17*mm] + [15.5*mm]*11, header=["P/E TTM", "P/E 27E", "P/E 28E", "EV/EBITDA 26", "EV/EBITDA 27E", "EV/EBITDA 28E",
                                                           "Rev CAGR 24-26", "EPS CAGR 27-29E", "ROCE 26 %", "EBITDA m 27E", "PEG 28"],
                      fmt={"pe_ttm": ".1f", "pe_fy27e": ".1f", "pe_fy28e": ".1f", "ev_ebitda_fy26": ".1f", "ev_ebitda_fy27e": ".1f",
                           "ev_ebitda_fy28e": ".1f", "rev_cagr_fy24_26_screener": pct0, "eps_cagr_fy27_29": pct0, "roce_fy26_pct": ".0f",
                           "ebitda_margin_fy27e": pct0, "peg_fy28": ".1f"}))
    st.append(Paragraph("B3. Cost-of-equity cross-examination (why the base Ke was NOT changed)", H))
    kr = tabs["ke_regression"]
    st.append(_ptable(kr[["raw_beta", "raw_beta_se", "blume_beta", "blume_ci95_low", "blume_ci95_high", "beta_implied_by_cmp", "implied_ke",
                          "tp_at_ci_low_beta", "tp_base", "tp_at_ci_high_beta", "cmp"]],
                      [17*mm] + [15.5*mm]*11, header=["Raw beta", "SE", "Blume beta", "CI95 low", "CI95 high", "Beta implied by CMP", "Implied Ke",
                                                      "TP @ CI low", "TP base", "TP @ CI high", "CMP"],
                      fmt={k: ".2f" for k in ["raw_beta", "raw_beta_se", "blume_beta", "blume_ci95_low", "blume_ci95_high", "beta_implied_by_cmp"]}
                      | {"implied_ke": ".1%", "tp_at_ci_low_beta": ".0f", "tp_base": ".0f", "tp_at_ci_high_beta": ".0f", "cmp": ".0f"}))
    bu = tabs["ke_bottom_up"]
    st.append(_ptable(bu[["n_firms", "levered_beta", "beta_used"] + [f"{t}_tp" for t in ["BSE", "CDSL", "CAMS", "KFINTECH"]]],
                      [45*mm] + [16*mm]*7, header=["Firms", "Levered beta", "Unlev. beta (cash-corr.)", "BSE TP", "CDSL TP", "CAMS TP", "KFin TP"],
                      fmt={"n_firms": ".0f", "levered_beta": ".2f", "beta_used": ".2f", "BSE_tp": ".0f", "CDSL_tp": ".0f", "CAMS_tp": ".0f", "KFINTECH_tp": ".0f"},
                      index_label="Damodaran India industry (Jan-2026)"))
    st.append(Paragraph(
        f"Decision rule (written after the bottom-up TPs below were computed, so judge it on its logic, not its timing): keep each firm's own 3-year regression beta unless a sourced alternative is consistent with it. Regression betas are "
        f"precise (SE {kr['raw_beta_se'].min():.2f}-{kr['raw_beta_se'].max():.2f}, 156 weeks). Damodaran's India dataset (DAMO_BETA_IN) has no exchange/depository/RTA bucket; "
        f"the candidate buckets span {bu['beta_used'].min():.2f}-{bu['beta_used'].max():.2f}, so picking one would be choosing the answer. For {w} only 'Information Services' "
        f"({bu.loc['Information Services','beta_used']:.2f}) is inside the 95% CI; it gives TP INR {bu.loc['Information Services', w + '_tp']:.0f} vs CMP {p['cmp']:.0f}. "
        f"The beta {w}'s price implies ({kr.loc[w,'beta_implied_by_cmp']:.2f}) lies below the CI. ERP alternatives (rating-based 7.08% with matching rf) are in the ERP x beta grid (Appendix D).", B))

    st.append(PageBreak())
    st.append(Paragraph("Appendix C - Financial due diligence", T))
    st.append(Paragraph("C1. PAT vs CFO vs FCF and working capital (Screener consolidated FY24-26, SCR_*)", H))
    eq = tabs["earnings_quality"]
    st.append(_ptable(eq, [17*mm] + [13.2*mm]*12,
                      header=["PAT 24-26", "CFO 24-26", "FCF 24-26", "CFO/PAT", "FCF/PAT", "CFO/PAT 24", "CFO/PAT 25", "CFO/PAT 26", "Debtor days 26",
                              "Debtor days 24", "ROCE 24", "ROCE 26"],
                      fmt={c: (".0f" if c.startswith(("pat", "cfo_fy", "fcf_fy", "debtor", "roce")) else ".2f") for c in eq.columns}))
    st.append(Paragraph("Reading: BSE's reported CFO includes clearing/settlement-fund movements (CFO/PAT 3.4x in FY24) - only owned cash enters our bridge. "
                        "CAMS converts profit to cash most reliably (no acquisitions, short receivables); KFin's debtor days and acquisition goodwill make its PAT "
                        "less cash-backed; CDSL is clean but cyclical.", B))
    st.append(Paragraph("C2. Governance, related parties, capitalisation and contingent items", H))
    g = tabs["governance"].set_index("ticker")
    st.append(_ptable(g, [17*mm, 105*mm, 42*mm, 22*mm], header=["Item", "Flag / why it matters", "Sources"]))
    st.append(Paragraph("C3. Moat and fragility summary", H))
    st.append(_ptable(tabs["moat"], [17*mm, 55*mm, 65*mm, 25*mm, 24*mm], header=["Moat", "Fragility", "Rating", "Sources"]))
    m3 = res["three_statement"]
    st.append(Paragraph(f"C4. {w} integrated three-statement model (INR cr) - balance sheet, cash flow and DCF tie", H))
    bs, cf = m3["bs"], m3["cf"]
    lines = pd.DataFrame({"Net fixed assets": bs["nfa"], "Treasury (cash+inv)": bs["treasury"], "Receivables": bs["rec"],
                          "Total assets": bs["total_assets"], "Total liabilities": bs["total_liabilities"],
                          "Equity incl. NCI": bs["total_equity_incl_nci"], "BS check (A-L-E)": bs["check"]}).T
    st.append(_grid(lines, "Balance sheet", cw=20*mm, f="{:.1f}"))
    cfl = pd.DataFrame({"PAT": cf["pat"], "CFO": cf["cfo"], "Capex": cf["capex"], "Dividends": cf["dividends"], "Net change in cash": cf["net_change"],
                        "Closing treasury": cf["closing_treasury"], "FCFF (3S)": cf["fcff_3s"], "FCFF (DCF engine)": cf["fcff_engine"]}).T
    st.append(_grid(cfl, "Cash flow", cw=20*mm, f="{:.1f}"))

    st.append(PageBreak())
    st.append(Paragraph("Appendix D - Scenarios and sensitivities (every number is a full model re-run)", T))
    sc = tabs["scenarios"].set_index(["ticker", "scenario"])[["rev_fy27e", "rev_fy28e", "ebitda_margin_fy28e", "eps_fy28e", "fcff_fy28e", "ev",
                                                               "value_ps", "target_price", "vs_cmp", "implied_pe_fy28e"]]
    sc.index = [f"{a} | {b}" for a, b in sc.index]
    st.append(_ptable(sc, [30*mm] + [15.5*mm]*10, header=["Rev 27E", "Rev 28E", "EBITDA m 28E", "EPS 28E", "FCFF 28E", "EV", "Value/sh",
                                                         "TP", "vs CMP", "P/E 28E at TP"],
                      fmt={"rev_fy27e": ".0f", "rev_fy28e": ".0f", "ebitda_margin_fy28e": pct0, "eps_fy28e": ".1f", "fcff_fy28e": ".0f",
                           "ev": ",.0f", "value_ps": ".0f", "target_price": ".0f", "vs_cmp": pct, "implied_pe_fy28e": ".1f"}, fs=5.8))
    st.append(Paragraph("Bear = derivatives turnover -30% and equity market -20% (persistent level shifts from Q3 FY27), growth -3pp FY28-31, g -1pp. "
                        "deriv_only / equity_only isolate each brief-mandated shock. Translation path: segment revenue x elasticity -> revenue; fixed costs do not flex -> margin; "
                        "EPS and FCFF follow; Ke unchanged except where stated; TP = model output.", S))
    st.append(Paragraph(f"D1. {w}: ERP x beta (rf paired with each ERP method)", H))
    st.append(_grid(tabs[f"sens_{w}_erp_beta"], "beta \\ ERP"))
    st.append(Paragraph(f"D2. {w}: business driver x market shock", H))
    st.append(_grid(tabs[f"sens_{w}_driver_x_market"], "growth \\ mkt shock"))
    st.append(Paragraph(f"D3. {w}: scenario-weight sensitivity of the probability-weighted TP", H))
    st.append(_ptable(tabs[f"sens_{w}_weights"], [10*mm, 18*mm, 18*mm, 18*mm, 20*mm], header=["w bear", "w base", "w bull", "PW TP"],
                      fmt={"w_bear": ".2f", "w_base": ".2f", "w_bull": ".2f", "pw_target": ".0f"}))
    st.append(Paragraph("D4. Tornado (12-month TP, INR) for all four", H))
    tor = []
    for t in ["CAMS", "KFINTECH", "BSE", "CDSL"]:
        x = tabs[f"sens_{t}_tornado"].head(4)
        for i, r in x.iterrows():
            tor.append(dict(k=f"{t} | {i}", lo=r.downside_tp, hi=r.upside_tp, rg=r["range"]))
    st.append(_ptable(pd.DataFrame(tor).set_index("k"), [80*mm, 18*mm, 18*mm, 18*mm], header=["TP low", "TP high", "Range"],
                      fmt={"lo": ".0f", "hi": ".0f", "rg": ".0f"}))

    st.append(PageBreak())
    st.append(Paragraph("Appendix E - Deployment timeline, fallback, liquidity; reproduction and sources", T))
    dt = dep["table"]
    cols = ["amount_cr", "entry_max", "drop_needed", "p_gbm_3m", "p_hist_3m", "p_gbm_6m", "p_hist_6m", "p_gbm_12m", "p_hist_12m", "days_to_fill"]
    st.append(_ptable(dt[cols], [20*mm] + [16*mm]*10, header=["INR cr", "Band", "Fall needed", "P 3m (model)", "3m (hist)", "P 6m (model)", "6m (hist)",
                                                             "P 12m (model)", "12m (hist)", "Days to fill"],
                      fmt={"amount_cr": ".0f", "entry_max": ".0f", "drop_needed": pct0, "days_to_fill": ".1f"} | {c: pct0 for c in cols if c.startswith("p_")}))
    eg, eh = dep["expected_deployed_gbm"], dep["expected_deployed_hist"]
    st.append(Paragraph(
        f"Expected INR cr deployed (sum of tranche x touch probability): model {eg['3m']:.0f} / {eg['6m']:.0f} / {eg['12m']:.0f} at 3 / 6 / 12 months; "
        f"history {eh['3m']:.0f} / {eh['6m']:.0f} / {eh['12m']:.0f}. Model = driftless log-normal barrier probability, sigma {dep['sigma']:.1%} from the last 252 sessions "
        f"of {dep['sym']}; history = all start dates {dep['hist_start']} to {dep['hist_end']} (overlapping windows, so not independent). T1 also waits for Q2 FY27 results. "
        f"Liquidity: average daily traded value INR {dep['liquidity']['adv_cr']:.0f} cr (median {dep['liquidity']['median_dv_cr']:.0f} cr) over "
        f"{dep['liquidity']['sessions']} sessions on {dep['liquidity']['venues']}; at {dep['liquidity']['participation']:.0%} participation INR 500 cr takes "
        f"~{dep['total_days_to_fill']:.0f} sessions; ticket = {p['ticket_pct_mcap']:.1%} of market cap.", B))
    st.append(Paragraph(
        "<b>Timeline and fallback.</b> Month 0-1: no purchase above the T1 band; wait for Q2 FY27 results (Nov-2026). Months 1-6: tranches fill only when bands trade, "
        f"at most {dep['liquidity']['participation']:.0%} of daily value. Month 6 (after Q4 FY27 results): re-run run_all.py on actuals; bands move only through the model. "
        "Month 12: capital still undeployed is returned to the fund's allocation, not forced into the stock and not parked in a sector index (every listed peer is above "
        "model value). Until then it sits in overnight/liquid funds. Exit/revisit triggers are in memo Section 5.", B))
    st.append(Paragraph("Reproduction", H))
    st.append(Paragraph("<font face='Courier'>./run_app.sh</font> (creates .venv from pinned requirements.txt, runs run_all.py, opens the offline Streamlit app) or "
                        "<font face='Courier'>make all &amp;&amp; make test</font>. Offline from data/raw; no API keys; optional FIRECRAWL_API_KEY only for refresh.", B))
    st.append(Paragraph("Sources (ID - description - accessed)", H))
    with open(ROOT / "data" / "sources.csv") as fh:
        src = list(csv.DictReader(fh))
    cs = S.clone("src", fontSize=5.9, leading=6.9)
    st.append(Paragraph(" | ".join(f"<b>{r['source_id']}</b>: {r['description'][:150]} ({r['access_date']})" for r in src), cs))
    return st


def build_report(res: dict, path: Path | None = None) -> Path:
    path = path or OUT / "submission_report.pdf"
    doc_for(path, "Zeckathon PS-01 submission report").build(memo_story(res) + appendix_story(res))
    return path
