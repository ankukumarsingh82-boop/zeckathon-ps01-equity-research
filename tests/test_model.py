import csv
from pathlib import Path

import pytest

from zk import ROOT
from zk.data import TICKERS, betas, facts, screener_table, v
from zk.engine import Scenario, dcf, forecast
from zk.scenarios import selection
from zk.sensitivity import wacc_g
from zk.three_statement import build

SCEN = ["base", "bear", "bull", "deriv_only", "equity_only"]


# ---------- 3-statement integrity ----------
@pytest.mark.parametrize("s", SCEN)
def test_balance_sheet_balances(s):
    bs = build(Scenario.named(s))["bs"]
    assert bs["check"].abs().max() < 1e-6


@pytest.mark.parametrize("s", SCEN)
def test_cash_ties(s):
    m = build(Scenario.named(s))
    assert (m["cf"]["closing_treasury"] - m["bs"]["treasury"].iloc[1:]).abs().max() < 1e-9
    opening = m["bs"]["treasury"].iloc[:-1].values
    assert abs((m["cf"]["net_change"].values - (m["bs"]["treasury"].iloc[1:].values - opening))).max() < 1e-9


@pytest.mark.parametrize("s", SCEN)
def test_fcff_identity_3s_equals_engine(s):
    cf = build(Scenario.named(s))["cf"]
    assert (cf["fcff_3s"] - cf["fcff_engine"]).abs().max() < 1e-6


def test_retained_earnings_roll():
    m = build()
    eq = m["bs"]["equity"]
    assert all(abs(eq.iloc[i + 1] - eq.iloc[i] - m["pl"]["pat"].iloc[i] + m["pl"]["dividends"].iloc[i]) < 1e-9 for i in range(5))


def test_opening_bs_matches_annual_report():
    B = facts()["cams_bs_mar26"]
    assets = sum(v(x) for k, x in B["assets"].items() if k != "total")
    assert abs(assets - v(B["assets"]["total"])) < 0.05           # AR total assets 1,810.38 cr
    liabs = sum(v(x) for k, x in B["liabilities"].items() if k != "total_liabilities")
    assert abs(liabs - v(B["liabilities"]["total_liabilities"])) < 0.05
    assert abs(build()["bs"]["equity"].iloc[0] - v(B["equity"]["equity_attributable"])) < 0.05


# ---------- data traceability ----------
def test_every_fact_has_known_source():
    ids = {r["source_id"] for r in csv.DictReader(open(ROOT / "data" / "sources.csv"))}

    def walk(n):
        if isinstance(n, dict):
            if "src" in n:
                yield n["src"]
            for x in n.values():
                yield from walk(x)
    used = set(walk(facts()))
    assert used, "no sourced facts found"
    assert used <= ids, f"facts reference undefined sources: {used - ids}"


def test_sources_have_url_and_access_date():
    for r in csv.DictReader(open(ROOT / "data" / "sources.csv")):
        assert r["url"].startswith("http"), r["source_id"]
        assert r["access_date"], r["source_id"]


@pytest.mark.parametrize("t", ["CDSL", "CAMS", "KFINTECH"])
def test_screener_revenue_matches_facts(t):
    scr = screener_table(t, "profit-loss").loc["Sales", "Mar 2026"]
    assert abs(scr / v(facts()["companies"][t]["fy26"]["revenue"]) - 1) < 0.01


def test_segments_sum_to_ytd_revenue():
    for t in TICKERS:
        F = facts()["companies"][t]
        segsum = sum(v(x) for x in F["segments_ytd"].values())
        assert abs(segsum / v(F["ytd"]["revenue"]) - 1) < 0.03, t


def test_betas_reasonable_and_cmp_matches_cache():
    b = betas()
    assert ((b.raw_beta > 0.3) & (b.raw_beta < 3)).all()
    for t in TICKERS:
        assert abs(b.loc[t, "yahoo_price"] - v(facts()["companies"][t]["cmp"])) < 0.01


# ---------- valuation logic ----------
@pytest.mark.parametrize("t", TICKERS)
def test_scenario_ordering(t):
    tp = {s: dcf(t, Scenario.named(s))["target_price"] for s in ("bear", "base", "bull")}
    assert tp["bear"] < tp["base"] < tp["bull"]


@pytest.mark.parametrize("t", TICKERS)
def test_shocks_never_raise_value(t):
    base = dcf(t)["target_price"]
    assert dcf(t, Scenario.named("deriv_only"))["target_price"] <= base + 1e-9
    assert dcf(t, Scenario.named("equity_only"))["target_price"] <= base + 1e-9


def test_derivatives_shock_hits_bse_most():
    hit = {t: dcf(t, Scenario.named("deriv_only"))["target_price"] / dcf(t)["target_price"] - 1 for t in TICKERS}
    assert min(hit, key=hit.get) == "BSE"
    assert abs(hit["CAMS"]) < 1e-12  # no derivatives elasticity in CAMS segments


@pytest.mark.parametrize("t", TICKERS)
def test_wacc_g_grid_monotone(t):
    g = wacc_g(t)
    assert (g.diff(axis=0).iloc[1:] < 0).all().all()   # higher WACC -> lower value
    assert (g.diff(axis=1).iloc[:, 1:] > 0).all().all()  # higher g -> higher value


def test_target_price_is_model_output_and_reported():
    d = dcf("CAMS")
    assert d["target_price"] == pytest.approx(d["value_ps"] * (1 + d["ke"]) - d["dps12"])
    assert d["upside"] == pytest.approx(d["target_price"] / d["cmp"] - 1)


def test_ev_decomposition():
    for t in TICKERS:
        d = dcf(t)
        assert d["ev"] == pytest.approx(d["pv_explicit"] + d["pv_fade"] + d["pv_terminal"])
        assert 0.2 < d["tv_share"] < 0.7


def test_fy27_includes_reported_ytd():
    for t in TICKERS:
        F = facts()["companies"][t]
        assert forecast(t).loc["FY27E", "revenue"] > v(F["ytd"]["revenue"])


def test_selection_winner_is_deterministic():
    s1, s2 = selection(), selection()
    assert list(s1.index) == list(s2.index)
    assert s1.index[0] == "CAMS"


def test_outputs_memo_exists_after_run():
    p = ROOT / "outputs" / "IC_memo.pdf"
    if not p.exists():
        pytest.skip("run `python run_all.py` first")
    assert p.stat().st_size > 10_000
