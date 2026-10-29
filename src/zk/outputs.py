"""Write all model outputs (CSV + one XLSX workbook + summary JSON)."""
from __future__ import annotations

import json

import pandas as pd

from . import OUT
from .allocation import plan
from .data import TICKERS, betas
from .diligence import GOVERNANCE, MOAT, earnings_quality
from .engine import cost_of_equity, dcf, relative_table
from .scenarios import scenario_table, selection
from .sensitivity import all_grids, weights_sensitivity
from .three_statement import build
from .deployment import schedule
from .industry import REG_TIMELINE, STRUCTURE, concentration, fo_impact
from .ke_crosscheck import bottom_up_table, regression_table
from .data import facts, v


def dcf_summary() -> pd.DataFrame:
    rows = []
    for t in TICKERS:
        d = dcf(t); c = cost_of_equity(t)
        rows.append({k: d[k] for k in ["ticker", "ke", "beta", "g", "pv_explicit", "pv_fade", "pv_terminal", "tv_share", "ev",
                                         "net_cash", "associates", "nci", "dividends_since_bs", "equity", "shares", "value_ps",
                                         "dps12", "target_price", "cmp", "upside"]} | {"rf": c["rf"], "erp": c["erp"]}
                    | _share_basis(t))
    return pd.DataFrame(rows).set_index("ticker")


def _share_basis(t: str) -> dict:
    F = facts()["companies"][t]
    issued = v(F.get("shares_issued_cr", F["diluted_shares_cr"]))
    inc = v(F.get("dilutive_increment_cr", 0.0))
    return dict(shares_issued=issued, dilutive_increment=inc, shares_diluted=v(F["diluted_shares_cr"]),
                shares_src=F["diluted_shares_cr"]["src"] + ": " + F["diluted_shares_cr"]["ref"])


def _freeze_xlsx(path) -> None:
    """Make the workbook byte-reproducible: pin docProps timestamps and zip entry dates to the valuation date."""
    import re
    import zipfile
    stamp = f"{facts()['valuation_date']}T00:00:00Z"
    with zipfile.ZipFile(path) as z:
        items = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in items:
            if name == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*", lambda m: m.group(1) + stamp.encode(), data)
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, data)


def write_all() -> dict:
    OUT.mkdir(exist_ok=True)
    tabs: dict[str, pd.DataFrame] = {}
    tabs["dcf_summary"] = dcf_summary()
    tabs["betas"] = betas()
    tabs["relative"] = relative_table()
    tabs["scenarios"] = scenario_table()
    tabs["selection"] = selection()
    for t in TICKERS:
        tabs[f"forecast_{t}"] = dcf(t)["forecast"]
    m = build()
    tabs["CAMS_3S_PL"], tabs["CAMS_3S_BS"], tabs["CAMS_3S_CF"] = m["pl"], m["bs"], m["cf"]
    tabs["earnings_quality"] = earnings_quality()
    tabs["moat"] = MOAT
    tabs["governance"] = GOVERNANCE
    for k, g in all_grids().items():
        tabs[f"sens_{k}"] = g
    tabs["sens_CAMS_weights"] = weights_sensitivity("CAMS")
    p = plan()
    tabs["allocation"] = pd.DataFrame(p["tranches"])
    dep = schedule(p)
    tabs["deployment"] = dep["table"]
    tabs["liquidity"] = pd.DataFrame([dep["liquidity"] | {"ticker": p["winner"]}]).set_index("ticker")
    tabs["ke_regression"] = regression_table()
    tabs["ke_bottom_up"] = bottom_up_table()
    tabs["industry_structure"] = STRUCTURE
    tabs["regulatory_timeline"] = REG_TIMELINE
    tabs["fo_direct_vs_second_order"] = fo_impact()
    tabs["concentration"] = concentration()
    for k, df in tabs.items():
        df.to_csv(OUT / f"{k}.csv")
    with pd.ExcelWriter(OUT / "model_outputs.xlsx") as xw:
        for k, df in tabs.items():
            df.to_excel(xw, sheet_name=k[:31])
    _freeze_xlsx(OUT / "model_outputs.xlsx")
    summary = {k: (float(v) if hasattr(v, "__float__") and not isinstance(v, (list, dict, str)) else v)
               for k, v in p.items() if k != "selection"}
    summary["tranches"] = [{kk: (float(vv) if not isinstance(vv, str) else vv) for kk, vv in t.items()} for t in p["tranches"]]
    summary["deployment"] = {"expected_deployed_cr_gbm": dep["expected_deployed_gbm"], "expected_deployed_cr_hist": dep["expected_deployed_hist"],
                             "sigma": dep["sigma"], "adv_cr": dep["liquidity"]["adv_cr"], "days_to_fill_all": dep["total_days_to_fill"],
                             "review_months": dep["review_months"]}
    summary["shares_diluted"] = float(tabs["dcf_summary"].loc[p["winner"], "shares_diluted"])
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return dict(tabs=tabs, plan=p, three_statement=m, deploy=dep)
