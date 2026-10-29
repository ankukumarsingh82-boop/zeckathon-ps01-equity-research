"""INR 500 cr deployment plan for the winner. Every price level is a model output."""
from __future__ import annotations

from .data import assumptions, facts, v
from .engine import Scenario, dcf
from .scenarios import selection

TICKET_CR = 500.0


def plan() -> dict:
    sel = selection()
    win = sel.index[0]
    F = facts()["companies"][win]
    cmp_ = v(F["cmp"])
    base = dcf(win); bear = dcf(win, Scenario.named("bear")); bull = dcf(win, Scenario.named("bull"))
    pw_value_today = sum(assumptions()["scenario_weights"][s] * dcf(win, Scenario.named(s))["value_ps"] for s in ("bear", "base", "bull"))
    mcap = cmp_ * v(F["diluted_shares_cr"])
    tranches = [
        dict(tranche="T1 starter", amount_cr=100.0, entry_max=round(bull["value_ps"], 0),
             rule="<= bull-case intrinsic value today; only after Q2 FY27 results confirm AAUM-linked revenue run-rate"),
        dict(tranche="T2", amount_cr=150.0, entry_max=round((bull["value_ps"] + base["value_ps"]) / 2, 0),
             rule="<= midpoint of bull and base intrinsic value"),
        dict(tranche="T3", amount_cr=250.0, entry_max=round(base["value_ps"], 0),
             rule="<= base-case intrinsic value (expected return >= Ke)"),
    ]
    return dict(winner=win, cmp=cmp_, price_date=facts()["valuation_date"],
                tp_base=base["target_price"], tp_bear=bear["target_price"], tp_bull=bull["target_price"],
                upside_base=base["upside"], downside_bear=bear["upside"], upside_bull=bull["upside"],
                pw_target=sel.loc[win, "pw_target"], pw_value_today=pw_value_today,
                ke=base["ke"], implied_ke=sel.loc[win, "implied_ke"],
                ticket_pct_mcap=TICKET_CR / mcap, tranches=tranches,
                undeployed=("Held in overnight/liquid funds until bands hit; bands re-computed by the model after every results release; "
                            "hard review at deployment.review_months (after Q4 FY27); capital still undeployed after 12 months is returned to the fund, "
                            "not forced into the stock and not parked in an index proxy (all four listed peers trade above model value)."),
                selection=sel)
