"""Tests for the review-round logic: deployment odds, liquidity, diluted shares, Ke cross-check, industry tables, report, pins."""
import csv
import re
from math import log, sqrt
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest

from zk import OUT, ROOT
from zk.data import TICKERS, YAHOO_DAILY, betas, daily, facts, v
from zk.deployment import liquidity, schedule, touch_freq_empirical, touch_prob_gbm
from zk.engine import Scenario, dcf
from zk.industry import REG_TIMELINE, SECOND_ORDER_TESTS, STRUCTURE, concentration, fo_impact
from zk.ke_crosscheck import bottom_up_table, damodaran_india, regression_table

SRC_IDS = {r["source_id"] for r in csv.DictReader(open(ROOT / "data" / "sources.csv"))}


# ---------- deployment maths ----------
def test_touch_prob_bounds_and_monotone():
    assert touch_prob_gbm(1.0, 0.3, 1.0) == 1.0
    assert touch_prob_gbm(0.9, 0.3, 0.0) == 0.0
    ps = [touch_prob_gbm(r, 0.3, 0.5) for r in (0.95, 0.9, 0.8, 0.7)]
    assert all(0 <= p <= 1 for p in ps) and ps == sorted(ps, reverse=True)
    assert touch_prob_gbm(0.8, 0.3, 0.25) < touch_prob_gbm(0.8, 0.3, 1.0)
    assert touch_prob_gbm(0.8, 0.2, 1.0) < touch_prob_gbm(0.8, 0.4, 1.0)


def test_touch_prob_driftless_reflection_formula():
    b, s, T = 0.8, 0.3, 1.0
    assert touch_prob_gbm(b, s, T) == pytest.approx(2 * NormalDist().cdf(log(b) / (s * sqrt(T))), abs=1e-12)


def test_touch_prob_matches_monte_carlo():
    rng = np.random.default_rng(7)
    s, T, n, steps, b = 0.3, 0.5, 20000, 2000, 0.85
    dt = T / steps
    # Brownian bridge correction would be exact; with fine steps discrete monitoring is within ~1.5pp
    z = rng.standard_normal((n, steps)).astype(np.float32) * np.float32(s * sqrt(dt))
    hit = (np.cumsum(z, axis=1).min(axis=1) <= log(b)).mean()
    p = touch_prob_gbm(b, s, T)
    assert hit <= p + 0.01 and hit == pytest.approx(p, abs=0.025)


def test_touch_freq_empirical_synthetic():
    c = pd.Series([100, 95, 90, 100, 100, 100], dtype=float)
    # horizon 2: windows t=0..3; min(c[t+1..t+2])/c[t]: 0.90, 0.947, 1.0, 1.0
    f, n = touch_freq_empirical(c, 0.92, 2)
    assert n == 4 and f == pytest.approx(0.25)
    f, n = touch_freq_empirical(c, 0.95, 2)
    assert f == pytest.approx(0.5)


@pytest.fixture(scope="module")
def res():
    from zk.outputs import write_all
    return write_all()


def test_schedule_consistency(res):
    d, p = res["deploy"], res["plan"]
    t = d["table"]
    assert t["amount_cr"].sum() == pytest.approx(500)
    for k in ("3m", "6m", "12m"):
        assert t[f"p_gbm_{k}"].between(0, 1).all() and t[f"p_hist_{k}"].between(0, 1).all()
        assert t[f"p_gbm_{k}"].is_monotonic_decreasing  # deeper bands -> lower odds
        assert 0 <= d["expected_deployed_gbm"][k] <= 500
    assert (t["p_gbm_3m"] <= t["p_gbm_6m"]).all() and (t["p_gbm_6m"] <= t["p_gbm_12m"]).all()
    assert (t["entry_max"] < p["cmp"]).all()  # every band below CMP -> INR 0 at CMP, disclosed
    liq = d["liquidity"]
    assert t["days_to_fill"].to_numpy() == pytest.approx((t["amount_cr"] / (liq["participation"] * liq["adv_cr"])).to_numpy())


def test_liquidity_recomputes_from_raw():
    tot = None
    for sym in YAHOO_DAILY["CAMS"]:
        d = daily(sym).iloc[-60:]
        x = d["close"] * d["volume"] / 1e7
        tot = x if tot is None else tot.add(x, fill_value=0)
    assert liquidity("CAMS")["adv_cr"] == pytest.approx(tot.mean())
    assert liquidity("CAMS")["adv_cr"] > 0


# ---------- diluted shares ----------
@pytest.mark.parametrize("t", TICKERS)
def test_diluted_shares_identity(t):
    s = facts()["companies"][t]["shares"] if "shares" in facts()["companies"][t] else facts()["companies"][t]
    flat = {k: v(x) for k, x in s.items() if k in ("shares_issued_cr", "dilutive_increment_cr", "diluted_shares_cr")}
    if t in ("CAMS", "KFINTECH"):
        assert len(flat) == 3, flat
    if len(flat) == 3:
        assert flat["diluted_shares_cr"] == pytest.approx(flat["shares_issued_cr"] + flat["dilutive_increment_cr"], abs=1e-6)
        assert flat["dilutive_increment_cr"] >= 0


def test_cams_dilutive_increment_from_ar():
    from zk.outputs import _share_basis
    b = _share_basis("CAMS")
    assert b["dilutive_increment"] == pytest.approx((248_851_830 - 247_531_761) / 1e7, abs=1e-7)
    assert b["shares_diluted"] == pytest.approx(b["shares_issued"] + b["dilutive_increment"])
    assert b["shares_src"]


def test_dcf_summary_has_shares_diluted():
    s = pd.read_csv(OUT / "dcf_summary.csv", index_col=0)
    assert "shares_diluted" in s.columns or "shares_diluted" in s.index


# ---------- Ke cross-check ----------
def test_damodaran_values_and_monotone_tp():
    d = damodaran_india()
    assert d.loc["Information Services", "Unlevered beta corrected for cash"] == pytest.approx(1.023, abs=0.001)
    bu = bottom_up_table().sort_values("beta_used")
    for t in TICKERS:
        assert bu[f"{t}_tp"].is_monotonic_decreasing  # higher beta -> lower TP


def test_ci_contains_point_and_base_ke_unchanged():
    b = betas()
    assert ((b["blume_ci95_low"] < b["blume_beta"]) & (b["blume_beta"] < b["blume_ci95_high"])).all()
    for t in TICKERS:  # base case uses the regression beta, not a cross-check beta
        assert dcf(t)["beta"] == pytest.approx(b.loc[t, "blume_beta"])


def test_cams_claims_in_memo_hold():
    r = regression_table().loc["CAMS"]
    assert r["beta_implied_by_cmp"] < r["blume_ci95_low"]  # memo: implied beta outside CI
    bu = bottom_up_table()
    inside = bu[(bu.beta_used >= r.blume_ci95_low) & (bu.beta_used <= r.blume_ci95_high)]
    assert list(inside.index) == ["Information Services"]
    assert (inside["CAMS_tp"] < r["cmp"]).all()  # memo: still below CMP


# ---------- industry ----------
def _ids(s):
    return [x.strip() for x in re.split(r"[,;]", s) if x.strip()]


def test_industry_sources_exist():
    used = set()
    for df in (STRUCTURE if isinstance(STRUCTURE, pd.DataFrame) else pd.DataFrame(STRUCTURE), REG_TIMELINE, concentration()):
        for s in df["src"]:
            used |= set(_ids(s))
    assert used and used <= SRC_IDS, used - SRC_IDS


def test_market_shares_sourced():
    for k, x in facts()["market_shares"].items():
        assert x["src"] in SRC_IDS
    c = concentration()
    assert c.loc["Depository (demat accounts)", "hhi_two_player"] == pytest.approx(80 ** 2 + 20 ** 2)


def test_level_mult_monotone():
    for t, (_, ov) in SECOND_ORDER_TESTS.items():
        k = next(iter(ov))
        lo = dcf(t, Scenario(name="lo", overrides={k: 0.9}))["target_price"]
        hi = dcf(t, Scenario(name="hi", overrides={k: 1.1}))["target_price"]
        base = dcf(t)["target_price"]
        assert lo < base < hi


def test_fo_direct_only_bse_material():
    f = fo_impact()
    assert f.loc["CAMS", "direct_tp_change"] == pytest.approx(0, abs=1e-9)
    assert f.loc["KFINTECH", "direct_tp_change"] == pytest.approx(0, abs=1e-9)
    assert f["direct_tp_change"].idxmin() == "BSE"
    assert f.loc["BSE", "deriv_weighted_rev_share_fy27e"] > 0.5


# ---------- deliverables ----------
def _pages(p):
    return len(re.findall(rb"/Type\s*/Page[^s]", p.read_bytes()))


def test_memo_two_pages_report_max_eight():
    assert _pages(OUT / "IC_memo.pdf") == 2
    n = _pages(OUT / "submission_report.pdf")
    assert 2 < n <= 8


def test_requirements_exactly_pinned():
    for f in ("requirements.txt", "requirements.lock"):
        lines = [l.strip() for l in open(ROOT / f) if l.strip() and not l.startswith("#")]
        assert lines and all(re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[0-9A-Za-z.\-+]+", l) for l in lines), f


def test_memo_price_note_is_honest():
    import subprocess
    txt = subprocess.run(["pdftotext", str(OUT / "IC_memo.pdf"), "-"], capture_output=True, text=True).stdout
    if not txt:
        pytest.skip("pdftotext unavailable")
    assert "15:29 IST" in txt and "bhavcopy" in txt and "NSE close" not in txt


def test_xlsx_is_byte_reproducible():
    import hashlib
    from zk.outputs import _freeze_xlsx
    p = OUT / "model_outputs.xlsx"
    h0 = hashlib.md5(p.read_bytes()).hexdigest()
    _freeze_xlsx(p)
    assert hashlib.md5(p.read_bytes()).hexdigest() == h0
