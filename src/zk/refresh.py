"""OPTIONAL online refresh of source pages. The model never needs this: it runs fully offline from data/raw.

Enabled only when FIRECRAWL_API_KEY is set. Without it this is a no-op (exit 0).
  python -m zk.refresh            # download fresh copies into data/refresh/<date>/ (does not touch the model inputs)
  python -m zk.refresh --apply    # also copy Screener/Yahoo files into data/raw and re-pin CMP + valuation_date in facts.yaml
Hand-transcribed filing facts (data/inputs/facts.yaml) are never changed automatically except CMP/valuation_date.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date

import requests

from . import INPUTS, RAW, ROOT

SCREENER = {t: f"https://www.screener.in/company/{t}/consolidated/" for t in ["BSE", "CDSL", "CAMS", "KFINTECH"]}
YAHOO = ["BSE.NS", "CDSL.NS", "CAMS.NS", "KFINTECH.NS", "^NSEI"]
FC_URL = "https://api.firecrawl.dev/v2/scrape"


def firecrawl_raw_html(url: str, key: str) -> str:
    r = requests.post(FC_URL, headers={"Authorization": f"Bearer {key}"},
                      json={"url": url, "formats": ["rawHtml"], "onlyMainContent": False}, timeout=120)
    r.raise_for_status()
    return r.json()["data"]["rawHtml"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        print("FIRECRAWL_API_KEY not set -> refresh skipped. The model runs from cached data in data/raw (offline).")
        return 0
    today = date.today().isoformat()
    out = ROOT / "data" / "refresh" / today
    out.mkdir(parents=True, exist_ok=True)
    for t, u in SCREENER.items():
        (out / f"screener_{t}.html").write_text(firecrawl_raw_html(u, key))
        print("fetched", u)
    for s in YAHOO:
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{s}?range=3y&interval=1wk"
        r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=60); r.raise_for_status()
        name = "IDX_NSEI" if s == "^NSEI" else s
        (out / f"yahoo_{name}.json").write_text(r.text)
        print("fetched", u)
    if a.apply:
        for f in out.iterdir():
            shutil.copy2(f, RAW / f.name)
        fy = INPUTS / "facts.yaml"
        txt = fy.read_text()
        for t, sym in {"BSE": "BSE.NS", "CDSL": "CDSL.NS", "CAMS": "CAMS.NS", "KFINTECH": "KFINTECH.NS"}.items():
            px = json.loads((RAW / f"yahoo_{sym}.json").read_text())["chart"]["result"][0]["meta"]["regularMarketPrice"]
            txt = re.sub(rf'(cmp: \{{value: )[0-9.]+(, src: YF, ref: "yahoo_{re.escape(sym)}\.json)', rf"\g<1>{px}\2", txt)
        txt = re.sub(r'valuation_date: "?[0-9-]+"?', f'valuation_date: "{today}"', txt, count=1)
        fy.write_text(txt)
        print("applied: data/raw updated; CMP and valuation_date re-pinned. Re-run `python run_all.py` and update sources.csv access dates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
