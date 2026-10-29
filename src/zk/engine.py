"""Comparable driver-based forecast + FCFF DCF for all four companies (identical structure).

Revenue: segment run-rates from the latest reported quarter(s), shocked by
  factor = (1 + e_d * deriv_shock) * (1 + e_m * market_shock)
for quarters not yet reported, then segment growth FY28-FY31, then fade to g.
Costs: fixed (calibrated from latest quarter, grows at fixed_cost_growth) + variable (% revenue).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from .data import assumptions, betas, facts, v, valuation_date

YEARS = ["FY27E", "FY28E", "FY29E", "FY30E", "FY31E"]
FY27_END = date(2027, 3, 31)


@dataclass
class Scenario:
    name: str = "base"
    deriv_shock: float = 0.0
    market_shock: float = 0.0
    growth_delta: float = 0.0
    g_delta: float = 0.0
    wacc_delta: float = 0.0
    overrides: dict = field(default_factory=dict)  # e.g. {"CAMS.mf_asset_based.growth": 0.10, "BSE.realisation_mult": 0.9}

    @classmethod
    def named(cls, name: str, **kw) -> "Scenario":
        s = assumptions()["scenarios"][name]
        base = dict(name=name, deriv_shock=s["deriv_shock"], market_shock=s["market_shock"],
                    growth_delta=s["growth_delta"], g_delta=s["g_delta"])
        base.update(kw)
        return cls(**base)


def _ov(sc: Scenario, key: str, default):
    return sc.overrides.get(key, default)


def cost_of_equity(ticker: str, sc: Scenario | None = None) -> dict:
    a = assumptions()["market"]
    sc = sc or Scenario()
    rf = _ov(sc, "rf", v(a["gsec_10y"]) - v(a["sovereign_default_spread"]))
    erp = _ov(sc, "erp", v(a["erp"]))
    beta = _ov(sc, f"{ticker}.beta", float(betas().loc[ticker, "blume_beta"]))
    ke = rf + beta * erp + sc.wacc_delta
    return dict(rf=rf, erp=erp, beta=beta, ke=ke, wacc=ke)  # net-cash firms, lease debt immaterial -> WACC = Ke


def _segment_fy27(ticker: str, sc: Scenario) -> dict[str, float]:
    """FY27E segment revenue = YTD actual + remaining quarters (shocked from Q3 onwards)."""
    F = facts()["companies"][ticker]
    A = assumptions()["companies"][ticker]
    nq = F["ytd"]["quarters"]
    out = {}
    for seg, cfg in A["segments"].items():
        ytd = v(F["segments_ytd"][seg])
        shock = (1 + cfg["e_d"] * sc.deriv_shock) * (1 + cfg["e_m"] * sc.market_shock)
        shock *= _ov(sc, f"{ticker}.{seg}.level_mult", 1.0)  # segment-specific persistent level shift (2nd-order tests)
        if ticker == "BSE" and seg == "eq_derivatives":
            d = F["derivatives"]
            r = ytd / (v(d["q1_adpt_cr"]) * v(d["q1_days"])) * _ov(sc, "BSE.realisation_mult", 1.0)
            adpt = v(d["q2_qtd_adpt_cr"])
            q2 = adpt * v(d["q2_days"]) * r
            h2 = adpt * v(A["derivatives_h2_adpt_vs_q2"]) * _ov(sc, "BSE.h2_adpt_mult", 1.0) * 125 * r * shock
            out[seg] = ytd + q2 + h2
            continue
        if nq == 1:  # Q2 elapsed (unreported): run-rate unshocked; Q3-Q4 shocked
            rr = ytd
            out[seg] = ytd + rr + 2 * rr * shock
        else:       # H1 reported: Q3-Q4 shocked
            rr = v(F["segments_last_q"][seg])
            out[seg] = ytd + 2 * rr * shock
    return out


def forecast(ticker: str, sc: Scenario | None = None) -> pd.DataFrame:
    """Explicit FY27E-FY31E P&L/FCFF (INR cr)."""
    sc = sc or Scenario()
    F = facts()["companies"][ticker]
    A = assumptions()["companies"][ticker]
    M = assumptions()["market"]
    tax = v(M["tax_rate"])
    fcg = _ov(sc, "fixed_cost_growth", v(M["fixed_cost_growth"]))
    nq = F["ytd"]["quarters"]
    ytd = F["ytd"]
    # latest-quarter cost calibration
    lq_rev = v(F["last_q"]["revenue"]) if "last_q" in F else v(ytd["revenue"])
    lq_opex = v(F["last_q"]["opex_ex_da"]) if "last_q" in F else v(ytd["opex_ex_da"])
    var_pct = v(ytd["variable_opex"]) / v(ytd["revenue"])
    var_pct = _ov(sc, f"{ticker}.var_pct", var_pct)
    fixed_q = lq_opex - var_pct * lq_rev
    da_pct = v(F["fy26"]["da"]) / v(F["fy26"]["revenue"])
    capex_pct = _ov(sc, f"{ticker}.capex_pct", v(A["capex_pct"]))
    nwc_pct = v(A["nwc_pct_incr_rev"])

    seg27 = _segment_fy27(ticker, sc)
    rows = []
    segs = dict(seg27)
    prev_rev = v(F["fy26"]["revenue"])
    fixed_annual = None
    for i, y in enumerate(YEARS):
        if i > 0:
            segs = {s: segs[s] * (1 + _ov(sc, f"{ticker}.{s}.growth", A["segments"][s]["growth"]) + sc.growth_delta)
                    for s in segs}
        rev = sum(segs.values())
        if i == 0:
            rem_q = 4 - nq
            fixed27 = fixed_q * rem_q
            opex = v(ytd["opex_ex_da"]) + fixed27 + var_pct * (rev - v(ytd["revenue"]))
            fixed_annual = fixed_q * 4 * (1 + fcg)
        else:
            opex = fixed_annual + var_pct * rev
            fixed_annual *= (1 + fcg)
        ebitda = rev - opex
        da = da_pct * rev
        ebit = ebitda - da
        capex = capex_pct * rev
        dnwc = nwc_pct * (rev - prev_rev)
        fcff = ebit * (1 - tax) + da - capex - dnwc
        row = dict(year=y, revenue=rev, opex=opex, ebitda=ebitda, ebitda_margin=ebitda / rev, da=da, ebit=ebit,
                   nopat=ebit * (1 - tax), capex=capex, dnwc=dnwc, fcff=fcff)
        row.update({f"seg_{k}": val for k, val in segs.items()})
        rows.append(row)
        prev_rev = rev
    return pd.DataFrame(rows).set_index("year")


def net_cash_bridge(ticker: str, sc: Scenario | None = None) -> dict:
    sc = sc or Scenario()
    B = facts()["companies"][ticker]["bridge"]
    cash = v(B["owned_cash_bank"]) + v(B["owned_investments"])
    liabs = v(B["owned_current_fin_liab"]) + v(B["statutory_remittances"]) + v(B["current_tax_liab"])
    debt = v(B["lease_debt"]) + v(B.get("debt_like_other", 0.0))
    stakes = v(B["other_associates_book"])
    cdsl_stake = 0.0
    if "cdsl_shares_held_cr" in B:
        cdsl_px = _ov(sc, "CDSL.price_for_stake", v(facts()["companies"]["CDSL"]["cmp"]))
        cdsl_stake = v(B["cdsl_shares_held_cr"]) * cdsl_px
    return dict(surplus_cash=cash, operating_liabs_funded_by_cash=liabs, debt_and_debt_like=debt,
                associates_book=stakes, cdsl_stake_market=cdsl_stake, nci=v(B["nci_book"]),
                dividends_paid_since_bs=v(B["dividends_paid_since_bs"]),
                net_cash=cash - liabs - debt)


def dcf(ticker: str, sc: Scenario | None = None) -> dict:
    sc = sc or Scenario()
    F = facts()["companies"][ticker]
    A = assumptions()["companies"][ticker]
    M = assumptions()["market"]
    tax = v(M["tax_rate"])
    fc = forecast(ticker, sc)
    coe = cost_of_equity(ticker, sc)
    w = coe["wacc"]
    g = _ov(sc, "g", v(M["terminal_growth"])) + sc.g_delta
    vd = valuation_date()
    bs_date = date.fromisoformat(F["bs_date"])
    stub = (FY27_END - vd).days / 365.0                       # FY27 time remaining after valuation date
    fy27_from_bs = (FY27_END - bs_date).days / 365.0          # share of FY27 after balance-sheet date
    elapsed = (vd - bs_date).days / 365.0                     # bs date -> valuation date (cash already earned)
    f27 = fc.loc["FY27E", "fcff"] * fy27_from_bs
    pv = f27 * (elapsed / fy27_from_bs)                       # undiscounted (already accrued)
    pv += f27 * (stub / fy27_from_bs) / (1 + w) ** (stub / 2)
    flows = []
    for i, y in enumerate(YEARS[1:], start=1):
        t = stub + i - 0.5
        pv += fc.loc[y, "fcff"] / (1 + w) ** t
        flows.append((y, fc.loc[y, "fcff"], t))
    # fade stage: growth linear from FY31 revenue growth to g; FCFF margin held at FY31 level
    last = fc.iloc[-1]
    g31 = fc["revenue"].iloc[-1] / fc["revenue"].iloc[-2] - 1
    fcff_margin = last["fcff"] / last["revenue"]
    rev = last["revenue"]
    nfade = int(v(M["fade_years"]))
    t = stub + len(YEARS) - 1 - 0.5
    pv_fade = 0.0
    for k in range(1, nfade + 1):
        gk = g31 + (g - g31) * k / nfade
        rev *= 1 + gk
        t += 1
        pv_fade += rev * fcff_margin / (1 + w) ** t
    if w <= g:
        raise ValueError("WACC must exceed g")
    tv = rev * fcff_margin * (1 + g) / (w - g)
    pv_tv = tv / (1 + w) ** (t + 0.5)
    ev = pv + pv_fade + pv_tv
    br = net_cash_bridge(ticker, sc)
    equity = (ev + br["net_cash"] + br["associates_book"] + br["cdsl_stake_market"] - br["nci"]
              - br["dividends_paid_since_bs"])
    shares = v(F["diluted_shares_cr"])
    value_ps = equity / shares
    # 12-month target = value rolled forward at Ke less dividends expected over next 12 months
    eps = eps_path(ticker, sc, fc)
    payout = v(A["payout"])
    dps12 = payout * (0.42 * eps["FY27E"] + 0.58 * eps["FY28E"])
    tp = value_ps * (1 + coe["ke"]) - dps12
    cmp_ = v(F["cmp"])
    return dict(ticker=ticker, scenario=sc.name, wacc=w, ke=coe["ke"], beta=coe["beta"], g=g,
                pv_explicit=pv, pv_fade=pv_fade, pv_terminal=pv_tv, tv_share=pv_tv / ev, ev=ev,
                net_cash=br["net_cash"], associates=br["associates_book"] + br["cdsl_stake_market"],
                nci=br["nci"], dividends_since_bs=br["dividends_paid_since_bs"], equity=equity,
                shares=shares, value_ps=value_ps, dps12=dps12, target_price=tp, cmp=cmp_,
                upside=tp / cmp_ - 1, eps=eps, forecast=fc)


def eps_path(ticker: str, sc: Scenario, fc: pd.DataFrame | None = None) -> dict:
    """EPS incl. treasury income (yield x surplus cash, held at bridge level) and associates run-rate."""
    F = facts()["companies"][ticker]
    M = assumptions()["market"]
    fc = forecast(ticker, sc) if fc is None else fc
    tax = v(M["tax_rate"])
    br = net_cash_bridge(ticker, sc)
    y = v(M["cash_yield"])
    assoc = v(F["ytd"]["associates"]) / F["ytd"]["quarters"] * 4
    out = {}
    cash = br["surplus_cash"] - br["operating_liabs_funded_by_cash"] - br["dividends_paid_since_bs"]
    payout = v(assumptions()["companies"][ticker]["payout"])
    for yname, r in fc.iterrows():
        oi = y * max(cash, 0)
        pat = (r["ebit"] + oi) * (1 - tax) + assoc
        out[yname] = pat / v(F["diluted_shares_cr"])
        cash += pat * (1 - payout)
    return out


def relative_table(sc: Scenario | None = None) -> pd.DataFrame:
    """P/E and EV/EBITDA on CMP, plus growth and ROCE for comparison."""
    from .data import screener_table
    sc = sc or Scenario()
    rows = []
    for t in ["BSE", "CDSL", "CAMS", "KFINTECH"]:
        F = facts()["companies"][t]
        d = dcf(t, sc)
        cmp_ = d["cmp"]
        mcap = cmp_ * d["shares"]
        ev_mkt = mcap - d["net_cash"] - d["associates"] + d["nci"]
        fc = d["forecast"]
        pl = screener_table(t, "profit-loss")
        rat = screener_table(t, "ratios")
        roce = rat.loc["ROCE %", "Mar 2026"] if "ROCE %" in rat.index else np.nan
        rev24 = pl.loc["Sales", "Mar 2024"]
        eps_ttm = pl.loc["EPS in Rs", "TTM"]
        rows.append(dict(ticker=t, cmp=cmp_, mcap_cr=mcap, ev_cr=ev_mkt,
                         pe_ttm=cmp_ / eps_ttm, pe_fy27e=cmp_ / d["eps"]["FY27E"], pe_fy28e=cmp_ / d["eps"]["FY28E"],
                         ev_ebitda_fy26=ev_mkt / (v(F["fy26"]["revenue"]) - v(F["fy26"]["opex_ex_da"])),
                         ev_ebitda_fy27e=ev_mkt / fc.loc["FY27E", "ebitda"], ev_ebitda_fy28e=ev_mkt / fc.loc["FY28E", "ebitda"],
                         rev_cagr_fy24_26_screener=(pl.loc["Sales", "Mar 2026"] / rev24) ** 0.5 - 1,
                         eps_cagr_fy27_29=(d["eps"]["FY29E"] / d["eps"]["FY27E"]) ** 0.5 - 1,
                         roce_fy26_pct=roce, ebitda_margin_fy27e=fc.loc["FY27E", "ebitda_margin"],
                         peg_fy28=(cmp_ / d["eps"]["FY28E"]) / (100 * ((d["eps"]["FY29E"] / d["eps"]["FY27E"]) ** 0.5 - 1)),
                         dcf_value_ps=d["value_ps"], target_price=d["target_price"], upside=d["upside"]))
    return pd.DataFrame(rows).set_index("ticker")
