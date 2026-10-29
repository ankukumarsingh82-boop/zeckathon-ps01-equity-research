"""Integrated 3-statement model for the winner (CAMS), FY27E-FY31E, driven by engine.forecast().

Linkages
- Revenue / opex / D&A / capex come from the same driver engine as the DCF (one source of truth).
- Other income = cash_yield x opening treasury; interest = lease rate x lease liability.
- Working capital: total change = engine driver (nwc % of incremental revenue); receivables/payables/other op. liabilities
  at FY26 % of revenue, other operating assets (accrued income etc.) is the balancing NWC line.
- Earmarked (trust / unpaid-dividend) assets and liabilities held flat; lease liability held flat (renewals = repayments).
- Dividends = payout x PAT; treasury is the cash plug from the cash-flow statement.
Checks: balance sheet balances every year; CF closing treasury == BS treasury; FCFF == engine FCFF.
"""
from __future__ import annotations

import pandas as pd

from .data import assumptions, facts, v
from .engine import Scenario, YEARS, forecast


def build(sc: Scenario | None = None, ticker: str = "CAMS") -> dict[str, pd.DataFrame]:
    sc = sc or Scenario()
    F = facts()
    B = F["cams_bs_mar26"]
    C = F["companies"][ticker]
    M = assumptions()["market"]
    A = assumptions()["companies"][ticker]
    tax = v(M["tax_rate"]); y = v(M["cash_yield"]); payout = v(A["payout"])
    fc = forecast(ticker, sc)
    rev26 = v(C["fy26"]["revenue"])
    a, l, e = B["assets"], B["liabilities"], B["equity"]
    rec_pct = v(a["trade_receivables"]) / rev26
    pay_pct = v(l["trade_payables"]) / rev26
    ool_pct = v(l["other_operating_liabilities"]) / rev26
    lease = v(l["lease_and_borrowings"])
    lease_rate = v(C["fy26"]["interest"]) / lease
    assoc_q = v(C["ytd"]["associates"])
    open_ = dict(nfa=v(a["net_fixed_and_intangible"]), treasury=v(a["treasury"]), rec=v(a["trade_receivables"]),
                 ooa=v(a["other_operating_assets"]), earA=v(a["earmarked_assets"]), onoa=v(a["other_non_operating_assets"]),
                 lease=lease, pay=v(l["trade_payables"]), ool=v(l["other_operating_liabilities"]),
                 earL=v(l["earmarked_liabilities"]), taxL=v(l["tax_liabilities"]), nci=v(e["nci"]))
    open_["equity"] = (open_["nfa"] + open_["treasury"] + open_["rec"] + open_["ooa"] + open_["earA"] + open_["onoa"]
                       - open_["lease"] - open_["pay"] - open_["ool"] - open_["earL"] - open_["taxL"] - open_["nci"])
    pl, bs, cf = [], [], []
    prev = dict(open_)
    bs.append(dict(year="FY26A", **prev))
    for yname in YEARS:
        r = fc.loc[yname]
        rev = r["revenue"]
        oi = y * prev["treasury"]
        interest = lease_rate * lease
        pbt = r["ebit"] + oi - interest
        tx = tax * pbt
        assoc = 4 * assoc_q
        pat = pbt - tx + assoc
        div = payout * pat
        cur = dict(prev)
        cur["nfa"] = prev["nfa"] + r["capex"] - r["da"]
        # NWC change is the engine's driver (nwc_pct x incremental revenue) so DCF and 3-statement share one FCFF.
        # Receivables / payables / other op. liabilities scale with revenue; other operating assets absorb the balance.
        d_nwc = r["dnwc"]
        cur["rec"] = rec_pct * rev; cur["pay"] = pay_pct * rev; cur["ool"] = ool_pct * rev
        nwc_prev = prev["rec"] + prev["ooa"] - prev["pay"] - prev["ool"]
        cur["ooa"] = nwc_prev + d_nwc - cur["rec"] + cur["pay"] + cur["ool"]
        cur["onoa"] = prev["onoa"] + assoc            # associate share accretes to investment carrying value
        cfo = pat - assoc + r["da"] - d_nwc
        cfi = -r["capex"]
        cff = -div
        cur["treasury"] = prev["treasury"] + cfo + cfi + cff
        cur["equity"] = prev["equity"] + pat - div
        pl.append(dict(year=yname, revenue=rev, opex=r["opex"], ebitda=r["ebitda"], da=r["da"], ebit=r["ebit"],
                       other_income=oi, interest=interest, pbt=pbt, tax=tx, associates=assoc, pat=pat,
                       eps=pat / v(C["diluted_shares_cr"]), dividends=div))
        cf.append(dict(year=yname, pat=pat, less_associates=-assoc, da=r["da"], change_nwc=-d_nwc, cfo=cfo,
                       capex=-r["capex"], cfi=cfi, dividends=-div, cff=cff, net_change=cfo + cfi + cff,
                       closing_treasury=prev["treasury"] + cfo + cfi + cff,
                       fcff_3s=cfo - r["capex"] - oi * (1 - tax) + interest * (1 - tax),
                       fcff_engine=r["fcff"], dnwc_engine=r["dnwc"]))
        bs.append(dict(year=yname, **cur))
        prev = cur
    bs = pd.DataFrame(bs).set_index("year")
    bs["total_assets"] = bs[["nfa", "treasury", "rec", "ooa", "earA", "onoa"]].sum(axis=1)
    bs["total_liabilities"] = bs[["lease", "pay", "ool", "earL", "taxL"]].sum(axis=1)
    bs["total_equity_incl_nci"] = bs["equity"] + bs["nci"]
    bs["check"] = bs["total_assets"] - bs["total_liabilities"] - bs["total_equity_incl_nci"]
    return dict(pl=pd.DataFrame(pl).set_index("year"), bs=bs, cf=pd.DataFrame(cf).set_index("year"),
                opening_equity_reported=v(e["equity_attributable"]))
