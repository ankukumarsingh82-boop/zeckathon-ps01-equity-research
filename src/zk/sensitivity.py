"""Sensitivity grids. Every cell is a full re-run of the DCF (no linear approximation)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TICKERS, assumptions, v
from .engine import Scenario, cost_of_equity, dcf

KEY_DRIVER = {  # (row override key, row values, label) per company: the business-specific driver
    "BSE": ("BSE.h2_adpt_mult", [0.6, 0.7, 0.85, 1.0, 1.15, 1.3], "H2 premium ADTV vs Q2 QTD (x)"),
    "CDSL": ("CDSL.transaction.growth", [0.04, 0.08, 0.12, 0.16, 0.20], "Transaction rev growth FY28-31"),
    "CAMS": ("CAMS.mf_asset_based.growth", [0.07, 0.10, 0.13, 0.16, 0.19], "MF asset-based rev growth FY28-31 (AAUM growth net of yield cut)"),
    "KFINTECH": ("KFINTECH.domestic_mf.growth", [0.07, 0.10, 0.13, 0.16, 0.19], "Domestic MF rev growth FY28-31"),
}


def wacc_g(ticker: str, wacc_steps=(-0.02, -0.01, 0.0, 0.01, 0.02), g_vals=(0.05, 0.055, 0.06, 0.065, 0.07, 0.075)) -> pd.DataFrame:
    base_w = cost_of_equity(ticker)["wacc"]
    out = {}
    for dw in wacc_steps:
        out[round(base_w + dw, 4)] = {g: dcf(ticker, Scenario(wacc_delta=dw, overrides={"g": g}))["target_price"] for g in g_vals}
    df = pd.DataFrame(out).T
    df.index.name = "WACC"; df.columns.name = "g"
    return df


def erp_beta(ticker: str, erps=(0.0523, 0.06, 0.0708), beta_deltas=(-0.3, -0.15, 0.0, 0.15, 0.3)) -> pd.DataFrame:
    b0 = cost_of_equity(ticker)["beta"]
    rf_alt = v(assumptions()["market"]["gsec_10y"]) - 0.0187  # rating-based default spread pairs with 7.08%
    out = {}
    for e in erps:
        rf = rf_alt if abs(e - 0.0708) < 1e-9 else None
        col = {}
        for db in beta_deltas:
            ov = {"erp": e, f"{ticker}.beta": b0 + db}
            if rf is not None:
                ov["rf"] = rf
            col[round(b0 + db, 2)] = dcf(ticker, Scenario(overrides=ov))["target_price"]
        out[f"ERP {e:.2%}"] = col
    df = pd.DataFrame(out); df.index.name = "beta"
    return df


def driver_x_market(ticker: str, shocks=(-0.3, -0.2, -0.1, 0.0, 0.1)) -> pd.DataFrame:
    key, vals, label = KEY_DRIVER[ticker]
    out = {}
    for x in vals:
        out[x] = {}
        for m in shocks:
            sc = Scenario(market_shock=m, overrides={key: x})
            if ticker == "BSE":
                sc = Scenario(market_shock=0.0, overrides={key: x, "BSE.realisation_mult": 1 + m})
            out[x][m] = dcf(ticker, sc)["target_price"]
    df = pd.DataFrame(out).T
    df.index.name = label
    df.columns.name = "realisation change" if ticker == "BSE" else "equity market shock"
    return df


def tornado(ticker: str) -> pd.DataFrame:
    base = dcf(ticker)["target_price"]
    m = assumptions()["market"]
    b0 = cost_of_equity(ticker)["beta"]
    cases = [
        ("Ke +/-100bp", Scenario(wacc_delta=0.01), Scenario(wacc_delta=-0.01)),
        ("Terminal g -/+50bp", Scenario(g_delta=-0.005), Scenario(g_delta=0.005)),
        ("Beta +/-0.2", Scenario(overrides={f"{ticker}.beta": b0 + 0.2}), Scenario(overrides={f"{ticker}.beta": b0 - 0.2})),
        ("Growth FY28-31 -/+3pp", Scenario(growth_delta=-0.03), Scenario(growth_delta=0.03)),
        ("Equity market -20%/+10%", Scenario(market_shock=-0.2), Scenario(market_shock=0.1)),
        ("Derivatives turnover -30%/+15%", Scenario(deriv_shock=-0.3), Scenario(deriv_shock=0.15)),
        ("Fixed-cost growth 13%/7%", Scenario(overrides={"fixed_cost_growth": 0.13}), Scenario(overrides={"fixed_cost_growth": 0.07})),
        ("Capex % rev +2pp/-2pp", Scenario(overrides={f"{ticker}.capex_pct": v(assumptions()["companies"][ticker]["capex_pct"]) + 0.02}),
         Scenario(overrides={f"{ticker}.capex_pct": v(assumptions()["companies"][ticker]["capex_pct"]) - 0.02})),
    ]
    rows = []
    for name, lo, hi in cases:
        a, b = dcf(ticker, lo)["target_price"], dcf(ticker, hi)["target_price"]
        rows.append(dict(driver=name, downside_tp=a, upside_tp=b, range=b - a, base_tp=base))
    return pd.DataFrame(rows).sort_values("range", ascending=False).set_index("driver")


def weights_sensitivity(ticker: str) -> pd.DataFrame:
    tps = {s: dcf(ticker, Scenario.named(s))["target_price"] for s in ("bear", "base", "bull")}
    rows = []
    for wb in (0.15, 0.25, 0.35, 0.5):
        wu = 0.25
        rows.append(dict(w_bear=wb, w_base=1 - wb - wu, w_bull=wu,
                         pw_target=wb * tps["bear"] + (1 - wb - wu) * tps["base"] + wu * tps["bull"]))
    return pd.DataFrame(rows)


def all_grids() -> dict[str, pd.DataFrame]:
    g = {}
    for t in TICKERS:
        g[f"{t}_wacc_g"] = wacc_g(t)
        g[f"{t}_driver_x_market"] = driver_x_market(t)
    for t in TICKERS:
        g[f"{t}_erp_beta"] = erp_beta(t)
        g[f"{t}_tornado"] = tornado(t)
    return g
