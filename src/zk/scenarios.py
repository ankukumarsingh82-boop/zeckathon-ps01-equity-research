"""Bull/base/bear + isolated stresses, probability-weighting, implied Ke, and winner selection."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TICKERS, assumptions, facts, v
from .engine import Scenario, dcf

SCEN = ["bear", "base", "bull", "deriv_only", "equity_only"]


def scenario_table() -> pd.DataFrame:
    rows = []
    for t in TICKERS:
        for s in SCEN:
            d = dcf(t, Scenario.named(s))
            fc = d["forecast"]
            rows.append(dict(ticker=t, scenario=s, rev_fy27e=fc.loc["FY27E", "revenue"], rev_fy28e=fc.loc["FY28E", "revenue"],
                             ebitda_margin_fy28e=fc.loc["FY28E", "ebitda_margin"], eps_fy27e=d["eps"]["FY27E"],
                             eps_fy28e=d["eps"]["FY28E"], fcff_fy28e=fc.loc["FY28E", "fcff"], ev=d["ev"],
                             value_ps=d["value_ps"], target_price=d["target_price"], cmp=d["cmp"], vs_cmp=d["upside"],
                             implied_pe_fy28e=d["target_price"] / d["eps"]["FY28E"]))
    return pd.DataFrame(rows)


def implied_ke(ticker: str) -> float:
    """Cost of equity at which base-case DCF value = CMP (bisection)."""
    cmp_ = v(facts()["companies"][ticker]["cmp"])
    base = dcf(ticker, Scenario())
    lo, hi = 0.07, 0.25
    for _ in range(60):
        mid = (lo + hi) / 2
        d = dcf(ticker, Scenario(wacc_delta=mid - base["ke"]))
        if d["value_ps"] > cmp_:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def selection() -> pd.DataFrame:
    w = assumptions()["scenario_weights"]
    st = scenario_table()
    rows = []
    for t in TICKERS:
        x = st[st.ticker == t].set_index("scenario")
        cmp_ = x.loc["base", "cmp"]
        div_yield = 0.0  # TP already net of dividends; add back dividend received by holder
        A = assumptions()["companies"][t]
        dps = v(A["payout"]) * x.loc["base", "eps_fy28e"]
        pw_tp = sum(w[s] * x.loc[s, "target_price"] for s in ("bear", "base", "bull"))
        exp_ret = (pw_tp + dps) / cmp_ - 1
        bear_dd = x.loc["bear", "target_price"] / cmp_ - 1
        base_ke = dcf(t)["ke"]
        ike = implied_ke(t)
        rows.append(dict(ticker=t, cmp=cmp_, tp_bear=x.loc["bear", "target_price"], tp_base=x.loc["base", "target_price"],
                         tp_bull=x.loc["bull", "target_price"], pw_target=pw_tp, exp_12m_total_return=exp_ret,
                         bear_vs_cmp=bear_dd, bear_tp_drop_vs_base=x.loc["bear", "target_price"] / x.loc["base", "target_price"] - 1,
                         capm_ke=base_ke, implied_ke=ike, ke_gap_bp=(base_ke - ike) * 1e4,
                         score=exp_ret - 0.5 * abs(min(bear_dd, 0))))
    df = pd.DataFrame(rows).set_index("ticker")
    df["rank"] = df["score"].rank(ascending=False).astype(int)
    return df.sort_values("rank")
