"""Load cached facts, assumptions and market data (fully offline)."""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
import yaml

from . import CONFIG, INPUTS, PROCESSED, RAW

TICKERS = ["BSE", "CDSL", "CAMS", "KFINTECH"]
YAHOO = {"BSE": "BSE.NS", "CDSL": "CDSL.NS", "CAMS": "CAMS.NS", "KFINTECH": "KFINTECH.NS"}


@lru_cache
def facts() -> dict:
    return yaml.safe_load((INPUTS / "facts.yaml").read_text())


@lru_cache
def assumptions() -> dict:
    return yaml.safe_load((CONFIG / "assumptions.yaml").read_text())


def v(node):
    """Return .value of a fact/assumption node (or the node if scalar)."""
    return node["value"] if isinstance(node, dict) and "value" in node else node


def valuation_date() -> date:
    return date.fromisoformat(facts()["valuation_date"])


def _yahoo_series(sym: str) -> tuple[pd.Series, dict]:
    d = json.loads((RAW / f"yahoo_{sym}.json").read_text())["chart"]["result"][0]
    ind = d["indicators"]
    closes = ind["adjclose"][0]["adjclose"] if "adjclose" in ind else ind["quote"][0]["close"]
    s = pd.Series(closes, index=pd.to_datetime(d["timestamp"], unit="s")).dropna()
    return s, d["meta"]


@lru_cache
def betas(years: int = 3) -> pd.DataFrame:
    idx, _ = _yahoo_series("IDX_NSEI")
    rows = []
    for t in TICKERS:
        s, meta = _yahoo_series(YAHOO[t])
        df = pd.concat([s, idx], axis=1, join="inner").pct_change().dropna()
        df = df[df.index >= df.index[-1] - pd.Timedelta(days=365 * years)]
        y, x = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
        raw = float(np.cov(y, x)[0, 1] / x.var(ddof=1))
        resid = y - y.mean() - raw * (x - x.mean())
        se = float(np.sqrt((resid ** 2).sum() / (len(x) - 2) / ((x - x.mean()) ** 2).sum()))
        rows.append(dict(ticker=t, raw_beta=raw, raw_beta_se=se, blume_beta=0.67 * raw + 0.33,
                         blume_ci95_low=0.67 * (raw - 1.96 * se) + 0.33, blume_ci95_high=0.67 * (raw + 1.96 * se) + 0.33,
                         n_weeks=len(df),
                         yahoo_price=meta["regularMarketPrice"],
                         price_time_utc=str(pd.to_datetime(meta["regularMarketTime"], unit="s"))))
    return pd.DataFrame(rows).set_index("ticker")


@lru_cache
def screener() -> pd.DataFrame:
    p = PROCESSED / "screener_long.csv"
    if not p.exists():
        from .parse_screener import main
        main()
    return pd.read_csv(p)


def screener_table(ticker: str, section: str) -> pd.DataFrame:
    d = screener()
    x = d[(d.ticker == ticker) & (d.section == section)]
    return x.pivot_table(index="item", columns="period", values="value", aggfunc="first")


YAHOO_DAILY = {"BSE": ["BSE.NS"], "CDSL": ["CDSL.NS"], "CAMS": ["CAMS.NS", "CAMS.BO"], "KFINTECH": ["KFINTECH.NS"]}


@lru_cache
def daily(sym: str) -> pd.DataFrame:
    """Yahoo daily OHLCV (split-adjusted by Yahoo), cached at data/raw/yahoo_daily_<sym>.json (source YF_DAILY)."""
    d = json.loads((RAW / f"yahoo_daily_{sym}.json").read_text())["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    idx = pd.to_datetime(d["timestamp"], unit="s").tz_localize("UTC").tz_convert("Asia/Kolkata").normalize().tz_localize(None)
    return pd.DataFrame({"close": q["close"], "volume": q["volume"]}, index=idx).dropna()
