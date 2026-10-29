"""Deployment timeline, fallback and liquidity for the INR 500 cr ticket.

Every number is an executable calculation on cached prices (YF_DAILY) and the model's tranche bands:
  * empirical touch frequency: share of historical start dates whose subsequent min close <= band/CMP within N sessions;
  * GBM barrier-touch probability (driftless log price by default, sigma from the last 252 daily returns);
  * liquidity: average daily traded value (NSE+BSE), days to fill each tranche at a capped participation rate.
These are frequencies/probabilities under stated assumptions, not forecasts.
"""
from __future__ import annotations

from math import exp, log, sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd

from .data import YAHOO_DAILY, assumptions, daily, v

N = NormalDist()


def touch_prob_gbm(ratio: float, sigma: float, t_years: float, log_drift: float = 0.0) -> float:
    """P(min_{0<=s<=T} S_s / S_0 <= ratio) for log-Brownian motion with drift `log_drift` and vol `sigma`."""
    if ratio >= 1.0:
        return 1.0
    if t_years <= 0:
        return 0.0
    b, s, m = log(ratio), sigma * sqrt(t_years), log_drift * t_years
    return N.cdf((b - m) / s) + exp(2 * log_drift * b / sigma ** 2) * N.cdf((b + m) / s)


def touch_freq_empirical(close: pd.Series, ratio: float, horizon: int) -> tuple[float, int]:
    """Share of start dates t with min(close[t+1..t+h]) / close[t] <= ratio (only windows fully inside history)."""
    c = close.to_numpy(dtype=float)
    n = len(c) - horizon
    if n <= 0:
        return float("nan"), 0
    fut_min = pd.Series(c[::-1]).rolling(horizon, min_periods=horizon).min().to_numpy()[::-1]  # min of c[t..t+h-1]
    hits = fut_min[1:n + 1] / c[:n] <= ratio
    return float(hits.mean()), int(n)


def ann_vol(close: pd.Series, window: int) -> float:
    r = np.log(close).diff().dropna().iloc[-window:]
    return float(r.std(ddof=1) * sqrt(252))


def liquidity(ticker: str) -> dict:
    D = assumptions()["deployment"]
    w = int(v(D["adv_window_days"]))
    tv = None
    for sym in YAHOO_DAILY[ticker]:
        d = daily(sym).iloc[-w:]
        x = (d["close"] * d["volume"]) / 1e7  # INR cr
        tv = x if tv is None else tv.add(x, fill_value=0.0)
    return dict(adv_cr=float(tv.mean()), median_dv_cr=float(tv.median()), sessions=len(tv),
                venues="+".join(YAHOO_DAILY[ticker]), participation=v(D["participation_rate"]))


def schedule(plan: dict) -> dict:
    """Tranche-level deployment odds + expected deployed amounts + days to fill."""
    D = assumptions()["deployment"]
    win, cmp_ = plan["winner"], plan["cmp"]
    sym = YAHOO_DAILY[win][0]
    px = daily(sym)["close"]
    yrs = int(v(D["history_years"]))
    hist = px[px.index >= px.index[-1] - pd.Timedelta(days=365 * yrs)]
    sigma = ann_vol(px, int(v(D["vol_window_days"])))
    mu = v(D["gbm_log_drift"])
    hz = v(D["horizons_trading_days"])
    liq = liquidity(win)
    cap_per_day = liq["participation"] * liq["adv_cr"]
    rows = []
    for t in plan["tranches"]:
        r = dict(tranche=t["tranche"], amount_cr=t["amount_cr"], entry_max=t["entry_max"],
                 drop_needed=t["entry_max"] / cmp_ - 1, days_to_fill=t["amount_cr"] / cap_per_day)
        for k, h in hz.items():
            r[f"p_gbm_{k}"] = touch_prob_gbm(t["entry_max"] / cmp_, sigma, h / 252, mu)
            r[f"p_hist_{k}"], r["n_windows_" + k] = touch_freq_empirical(hist, t["entry_max"] / cmp_, h)
        rows.append(r)
    tab = pd.DataFrame(rows).set_index("tranche")
    exp_dep = {k: float((tab["amount_cr"] * tab[f"p_gbm_{k}"]).sum()) for k in hz}
    exp_dep_hist = {k: float((tab["amount_cr"] * tab[f"p_hist_{k}"]).sum()) for k in hz}
    return dict(table=tab, sigma=sigma, sym=sym, hist_start=str(hist.index[0].date()), hist_end=str(hist.index[-1].date()),
                expected_deployed_gbm=exp_dep, expected_deployed_hist=exp_dep_hist, liquidity=liq,
                total_days_to_fill=float(tab["days_to_fill"].sum()), review_months=int(v(D["review_months"])))
