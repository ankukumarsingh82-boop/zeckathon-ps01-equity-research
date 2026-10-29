"""Cost-of-equity cross-examination: regression beta precision vs Damodaran India bottom-up industry betas.

The base case is NOT changed by this module. It shows how far each sourced alternative would move the target price
so the IC can see the Ke decision is not tuned (README: 'Ke decision').
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from . import RAW
from .data import TICKERS, assumptions, betas, v
from .engine import Scenario, cost_of_equity, dcf


@lru_cache
def damodaran_india() -> pd.DataFrame:
    """Industry Averages sheet of Damodaran betaIndia.xls (Jan-2026), cached at data/raw/damodaran_betaIndia.xls."""
    raw = pd.read_excel(RAW / "damodaran_betaIndia.xls", sheet_name="Industry Averages", header=None, engine="xlrd")
    hdr = raw.index[raw[0].astype(str).str.strip() == "Industry Name"][0]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c).strip() for c in raw.iloc[hdr]]
    df = df[df["Industry Name"].notna()].set_index("Industry Name")
    return df


def bottom_up_table() -> pd.DataFrame:
    C = assumptions()["ke_crosscheck"]
    col = v(C["beta_column"])
    d = damodaran_india()
    rows = []
    for ind in v(C["damodaran_india_candidates"]):
        b = float(d.loc[ind, col])
        r = dict(industry=ind, n_firms=int(d.loc[ind, "Number of firms"]), levered_beta=float(d.loc[ind, "Beta"]), beta_used=b)
        for t in TICKERS:
            sc = Scenario(name=f"bu_{ind}", overrides={f"{t}.beta": b})
            x = dcf(t, sc)
            r[f"{t}_ke"] = x["ke"]
            r[f"{t}_tp"] = x["target_price"]
        rows.append(r)
    return pd.DataFrame(rows).set_index("industry")


def regression_table() -> pd.DataFrame:
    b = betas()
    rows = []
    for t in TICKERS:
        base = dcf(t)
        lo = dcf(t, Scenario(name="beta_ci_low", overrides={f"{t}.beta": float(b.loc[t, "blume_ci95_low"])}))
        hi = dcf(t, Scenario(name="beta_ci_high", overrides={f"{t}.beta": float(b.loc[t, "blume_ci95_high"])}))
        ke0 = cost_of_equity(t)
        implied_beta = None
        from .scenarios import implied_ke
        ike = implied_ke(t)
        implied_beta = (ike - ke0["rf"]) / ke0["erp"]
        rows.append(dict(ticker=t, raw_beta=b.loc[t, "raw_beta"], raw_beta_se=b.loc[t, "raw_beta_se"],
                         blume_beta=b.loc[t, "blume_beta"], blume_ci95_low=b.loc[t, "blume_ci95_low"],
                         blume_ci95_high=b.loc[t, "blume_ci95_high"], n_weeks=b.loc[t, "n_weeks"],
                         tp_base=base["target_price"], tp_at_ci_low_beta=lo["target_price"], tp_at_ci_high_beta=hi["target_price"],
                         implied_ke=ike, beta_implied_by_cmp=implied_beta, cmp=base["cmp"]))
    return pd.DataFrame(rows).set_index("ticker")
