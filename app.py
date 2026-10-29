"""Zeckathon PS-01 local app. Run:  .venv/bin/streamlit run app.py   (or `make app`)
Fully offline: reads cached, sourced data in data/raw + data/inputs + config. No API keys required.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from zk.allocation import plan  # noqa: E402
from zk.data import TICKERS, assumptions, betas, facts, v  # noqa: E402
from zk.diligence import GOVERNANCE, MOAT, earnings_quality  # noqa: E402
from zk.engine import Scenario, cost_of_equity, dcf, net_cash_bridge, relative_table  # noqa: E402
from zk.scenarios import selection  # noqa: E402
from zk.sensitivity import driver_x_market, erp_beta, tornado, wacc_g  # noqa: E402
from zk.three_statement import build  # noqa: E402
from zk.deployment import schedule  # noqa: E402
from zk.industry import REG_TIMELINE, STRUCTURE, concentration, fo_impact  # noqa: E402
from zk.ke_crosscheck import bottom_up_table, regression_table  # noqa: E402

st.set_page_config(page_title="Zeckathon PS-01 | BSE vs CDSL vs CAMS vs KFin", layout="wide")
A, F = assumptions(), facts()
M = A["market"]

st.sidebar.header("Market inputs")
gsec = st.sidebar.slider("10y G-sec", 0.06, 0.09, float(v(M["gsec_10y"])), 0.0005, format="%.4f")
cds = st.sidebar.slider("Sovereign default spread (removed from G-sec)", 0.0, 0.02, float(v(M["sovereign_default_spread"])), 0.0005, format="%.4f")
erp = st.sidebar.slider("Equity risk premium", 0.04, 0.09, float(v(M["erp"])), 0.0005, format="%.4f")
g = st.sidebar.slider("Terminal growth g", 0.04, 0.08, float(v(M["terminal_growth"])), 0.0025, format="%.4f")
ke_adj = st.sidebar.slider("Ke adjustment (all firms)", -0.03, 0.03, 0.0, 0.0025, format="%.4f")
st.sidebar.header("Custom scenario (applied on top)")
preset = st.sidebar.selectbox("Start from", ["base", "bear", "bull", "deriv_only", "equity_only"])
p0 = A["scenarios"][preset]
dshock = st.sidebar.slider("Derivatives turnover shock", -0.6, 0.4, float(p0["deriv_shock"]), 0.05)
mshock = st.sidebar.slider("Equity market shock", -0.5, 0.3, float(p0["market_shock"]), 0.05)
gdelta = st.sidebar.slider("Segment growth delta FY28-31", -0.08, 0.06, float(p0["growth_delta"]), 0.005)
gd = st.sidebar.slider("Terminal g delta", -0.02, 0.01, float(p0["g_delta"]), 0.0025)
st.sidebar.header("Scenario weights")
wb = st.sidebar.slider("Bear", 0.0, 1.0, float(A["scenario_weights"]["bear"]), 0.05)
wu = st.sidebar.slider("Bull", 0.0, 1.0 - wb, float(A["scenario_weights"]["bull"]), 0.05)
wbase = 1 - wb - wu
st.sidebar.caption(f"Base weight = {wbase:.2f}")

ov = {"rf": gsec - cds, "erp": erp, "g": g}


def S(name=None, **kw):
    base = Scenario.named(name) if name else Scenario()
    return Scenario(name=base.name, deriv_shock=kw.get("d", base.deriv_shock), market_shock=kw.get("m", base.market_shock),
                    growth_delta=kw.get("gr", base.growth_delta), g_delta=kw.get("gd", base.g_delta), wacc_delta=ke_adj, overrides=dict(ov))


custom = S(d=dshock, m=mshock, gr=gdelta, gd=gd)

st.title("Zeckathon PS-01 — BSE vs CDSL vs CAMS vs KFin Technologies")
st.caption(f"Price/valuation date {F['valuation_date']} · INR · offline from cached sources (data/sources.csv) · every number recomputed live by the same engine as `run_all.py`")

rows = []
for t in TICKERS:
    tps = {s: dcf(t, S(s)) for s in ("bear", "base", "bull")}
    c = dcf(t, custom)
    pw = wb * tps["bear"]["target_price"] + wbase * tps["base"]["target_price"] + wu * tps["bull"]["target_price"]
    dps = v(A["companies"][t]["payout"]) * tps["base"]["eps"]["FY28E"]
    rows.append(dict(ticker=t, CMP=c["cmp"], Ke=c["ke"], TP_custom=c["target_price"], vs_CMP_custom=c["upside"],
                     TP_bear=tps["bear"]["target_price"], TP_base=tps["base"]["target_price"], TP_bull=tps["bull"]["target_price"],
                     PW_TP=pw, PW_total_return=(pw + dps) / c["cmp"] - 1, bear_vs_CMP=tps["bear"]["upside"]))
board = pd.DataFrame(rows).set_index("ticker")
board["score"] = board["PW_total_return"] - 0.5 * board["bear_vs_CMP"].clip(upper=0).abs()
board = board.sort_values("score", ascending=False)
win = board.index[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Winner (PW return - 0.5 x bear loss)", win)
c2.metric(f"{win} 12m target (custom scenario)", f"₹{board.loc[win,'TP_custom']:.0f}", f"{board.loc[win,'vs_CMP_custom']:+.1%} vs CMP ₹{board.loc[win,'CMP']:.2f}")
c3.metric("Bear / Bull TP", f"₹{board.loc[win,'TP_bear']:.0f} / ₹{board.loc[win,'TP_bull']:.0f}")
c4.metric("Prob-weighted 12m total return", f"{board.loc[win,'PW_total_return']:+.1%}")

tabs = st.tabs(["Scoreboard", "Company DCF", "Scenarios", "Sensitivities", "3-statement (winner)", "Diligence", "₹500 cr plan", "IC memo", "Sources & data", "Industry & F&O curbs", "Ke cross-check"])
pctcols = ["Ke", "vs_CMP_custom", "PW_total_return", "bear_vs_CMP", "score"]
with tabs[0]:
    st.dataframe(board.style.format({c: "{:.1%}" for c in pctcols} | {c: "{:,.0f}" for c in board.columns if c not in pctcols}), width="stretch")
    st.subheader("Relative valuation cross-check (base, CMP-based multiples)")
    st.dataframe(relative_table(S()).round(3), width="stretch")
    st.subheader("Betas (3y weekly vs Nifty 50, Blume-adjusted)")
    st.dataframe(betas().round(3), width="stretch")

with tabs[1]:
    t = st.selectbox("Company", TICKERS, index=TICKERS.index(win))
    d = dcf(t, custom)
    st.write(f"Ke {d['ke']:.2%} (beta {d['beta']:.2f}) · g {d['g']:.2%} · terminal value share of EV {d['tv_share']:.0%}")
    st.dataframe(d["forecast"].T.round(2), width="stretch")
    bridge = pd.Series({"PV explicit FY27-31": d["pv_explicit"], "PV fade FY32-41": d["pv_fade"], "PV terminal": d["pv_terminal"],
                        "Enterprise value": d["ev"], "+ owned net cash (after op. liabilities, debt-like)": d["net_cash"],
                        "+ associates / stakes": d["associates"], "- NCI": -d["nci"], "- dividends paid since BS date": -d["dividends_since_bs"],
                        "Equity value": d["equity"], "Diluted shares (cr)": d["shares"], "Value per share today": d["value_ps"],
                        "x (1+Ke) - next-12m DPS": d["dps12"], "12m target price": d["target_price"], "CMP": d["cmp"], "Upside": d["upside"]})
    st.dataframe(bridge.to_frame("INR cr / INR").style.format("{:,.2f}"), width="stretch")
    st.json({k: (v(x) if isinstance(x, dict) else x) for k, x in F["companies"][t]["bridge"].items()}, expanded=False)

with tabs[2]:
    sc_rows = []
    for t in TICKERS:
        for s in ["base", "bear", "bull", "deriv_only", "equity_only"]:
            d = dcf(t, S(s))
            sc_rows.append(dict(ticker=t, scenario=s, rev_FY28E=d["forecast"].loc["FY28E", "revenue"], ebitda_margin_FY28E=d["forecast"].loc["FY28E", "ebitda_margin"],
                                EPS_FY28E=d["eps"]["FY28E"], TP=d["target_price"], vs_CMP=d["upside"]))
    sc = pd.DataFrame(sc_rows)
    st.dataframe(sc.pivot(index="ticker", columns="scenario", values="TP").round(0), width="stretch")
    st.dataframe(sc.round(3), width="stretch")
    st.caption("bear = derivatives turnover -30% AND equity market -20% (persistent from Q3 FY27), growth -3pp, g -1pp. Definitions: config/assumptions.yaml")

with tabs[3]:
    t = st.selectbox("Company ", TICKERS, index=TICKERS.index(win))
    st.caption("Every cell is a full DCF re-run using the sidebar market inputs (base operating scenario).")
    with st.spinner("computing grids"):
        from zk import engine as E
        base_cost = cost_of_equity(t, S())
        grid = {}
        for dw in (-0.02, -0.01, 0.0, 0.01, 0.02):
            grid[f"{base_cost['ke'] + dw:.2%}"] = {f"{gg:.2%}": dcf(t, Scenario(wacc_delta=ke_adj + dw, overrides=ov | {"g": gg}))["target_price"]
                                                  for gg in (0.05, 0.055, 0.06, 0.065, 0.07, 0.075)}
        st.subheader("WACC x g (12m TP)")
        st.dataframe(pd.DataFrame(grid).T.round(0), width="stretch")
    st.subheader("ERP x beta (cached market inputs)")
    st.dataframe(erp_beta(t).round(0), width="stretch")
    st.subheader("Business driver x market / realisation")
    st.dataframe(driver_x_market(t).round(0), width="stretch")
    st.subheader("Tornado")
    st.dataframe(tornado(t).round(0), width="stretch")

with tabs[4]:
    m = build(custom)
    st.write(f"Max |assets - liabilities - equity| = {m['bs']['check'].abs().max():.2e} · max |FCFF(3S) - FCFF(DCF)| = "
             f"{(m['cf']['fcff_3s'] - m['cf']['fcff_engine']).abs().max():.2e} · CF closing cash = BS treasury")
    st.subheader("P&L"); st.dataframe(m["pl"].T.round(2), width="stretch")
    st.subheader("Balance sheet"); st.dataframe(m["bs"].T.round(2), width="stretch")
    st.subheader("Cash flow"); st.dataframe(m["cf"].T.round(2), width="stretch")
    st.caption("CAMS, opening BS = audited 31-Mar-2026 consolidated (CAMS AR FY26). Uses the custom scenario.")

with tabs[5]:
    st.subheader("Earnings quality FY24-26 (Screener consolidated)"); st.dataframe(earnings_quality().round(2), width="stretch")
    st.subheader("Moat"); st.dataframe(MOAT, width="stretch")
    st.subheader("Governance flags"); st.dataframe(GOVERNANCE, width="stretch")

with tabs[6]:
    p = plan()
    st.write(f"Winner (cached base inputs): **{p['winner']}** · CMP ₹{p['cmp']:.2f} ({p['price_date']}) · 12m TP ₹{p['tp_base']:.0f} "
             f"({p['upside_base']:+.1%}) · bear ₹{p['tp_bear']:.0f} · bull ₹{p['tp_bull']:.0f} · ticket = {p['ticket_pct_mcap']:.1%} of market cap")
    st.dataframe(pd.DataFrame(p["tranches"]), width="stretch")
    st.write(p["undeployed"])
    d = schedule(p)
    st.subheader("Deployment odds (all bands are below CMP: INR 0 deployed at CMP)")
    st.dataframe(d["table"].round(3), width="stretch")
    eg, eh = d["expected_deployed_gbm"], d["expected_deployed_hist"]
    st.write(f"Expected INR cr deployed - model: 3m {eg['3m']:.0f} / 6m {eg['6m']:.0f} / 12m {eg['12m']:.0f}; history: {eh['3m']:.0f} / {eh['6m']:.0f} / {eh['12m']:.0f}. "
             f"sigma {d['sigma']:.1%} ({d['sym']}), ADV INR {d['liquidity']['adv_cr']:.0f} cr ({d['liquidity']['venues']}), "
             f"INR 500 cr fills in ~{d['total_days_to_fill']:.0f} sessions at {d['liquidity']['participation']:.0%} participation. "
             f"Review at month {d['review_months']}; undeployed capital returned at month 12.")
    st.markdown("""**Exit / revisit triggers** — (1) MF AAUM share < 65% for two quarters or loss of a top-10 AMC → exit; (2) asset-based revenue growth > 5pp below AAUM growth for two quarters, or EBITDA margin < 42% → revisit/trim; (3) price above bull TP without bull drivers → trim.""")

with tabs[7]:
    pdf = ROOT / "outputs" / "IC_memo.pdf"
    if st.button("Regenerate outputs + memo (runs run_all.py, cached inputs)"):
        with st.spinner("running"):
            r = subprocess.run([sys.executable, str(ROOT / "run_all.py")], capture_output=True, text=True, cwd=ROOT)
            st.code(r.stdout + r.stderr)
    if pdf.exists():
        st.download_button("Download IC memo (PDF)", pdf.read_bytes(), file_name="IC_memo.pdf", mime="application/pdf")
        rep = ROOT / "outputs" / "submission_report.pdf"
        if rep.exists():
            st.download_button("Download full submission report (PDF, <= 8 pages)", rep.read_bytes(), file_name="submission_report.pdf", mime="application/pdf")
        try:
            out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=30).stdout
        except Exception:
            out = ""
        if out:
            st.text(out)
        else:
            st.info("Install poppler-utils to preview text here, or download the PDF.")
    else:
        st.warning("Memo not yet generated: click the button above or run `python run_all.py`.")

with tabs[8]:
    st.dataframe(pd.read_csv(ROOT / "data" / "sources.csv"), width="stretch")
    st.subheader("Optional online refresh")
    if os.environ.get("FIRECRAWL_API_KEY"):
        if st.button("Refresh Screener pages + prices (FIRECRAWL_API_KEY detected) into data/refresh/"):
            r = subprocess.run([sys.executable, "-m", "zk.refresh"], capture_output=True, text=True, cwd=ROOT, env=os.environ | {"PYTHONPATH": str(ROOT / "src")})
            st.code(r.stdout + r.stderr)
    else:
        st.info("FIRECRAWL_API_KEY not set — running fully offline from cached data (this is the default and needs no keys).")

with tabs[9]:
    st.subheader("Value chain, licences, market structure (sourced)"); st.dataframe(STRUCTURE, width="stretch")
    st.subheader("Concentration"); st.dataframe(concentration(), width="stretch")
    st.subheader("Regulatory timeline"); st.dataframe(REG_TIMELINE, width="stretch")
    st.subheader("SEBI F&O curbs: direct vs second-order (engine re-runs; second-order magnitudes are labelled what-ifs, not sourced)")
    st.dataframe(fo_impact().round(3), width="stretch")

with tabs[10]:
    st.subheader("Regression beta precision and the beta implied by CMP"); st.dataframe(regression_table().round(3), width="stretch")
    st.subheader("Damodaran India industry betas (Jan-2026) -> Ke and TP"); st.dataframe(bottom_up_table().round(3), width="stretch")
    st.caption("Base case keeps each company's own regression (Blume) beta; cross-check only. See README 'Cost-of-equity decision'.")
