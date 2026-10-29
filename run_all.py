"""One-command reproduction: parse cached data -> models -> outputs/ -> IC memo PDF -> checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from zk.parse_screener import main as parse  # noqa: E402
from zk.outputs import write_all  # noqa: E402
from zk.memo import build_memo  # noqa: E402
from zk.report import build_report  # noqa: E402

if __name__ == "__main__":
    parse()
    res = write_all()
    pdf = build_memo(res)
    rep = build_report(res)
    p = res["plan"]
    print(f"Winner: {p['winner']}  CMP {p['cmp']:.2f} ({p['price_date']})  12m TP {p['tp_base']:.0f} ({p['upside_base']:+.1%})"
          f"  bear {p['tp_bear']:.0f} ({p['downside_bear']:+.1%})  bull {p['tp_bull']:.0f} ({p['upside_bull']:+.1%})")
    d = res["deploy"]
    print(f"Expected deployment (model): 6m INR {d['expected_deployed_gbm']['6m']:.0f} cr, 12m INR {d['expected_deployed_gbm']['12m']:.0f} cr;"
          f" ADV INR {d['liquidity']['adv_cr']:.0f} cr")
    print(f"Outputs -> outputs/ ; memo -> {pdf} ; report -> {rep}")
