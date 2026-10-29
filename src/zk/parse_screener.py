"""Parse saved Screener.in consolidated pages (data/raw/screener_*.html) into tidy CSVs.

Each output row carries source_url and access_date so every number is traceable.
Values are INR crore exactly as displayed by Screener (consolidated)."""
from __future__ import annotations

import csv
import re

from bs4 import BeautifulSoup

from . import PROCESSED, RAW

TICKERS = ["BSE", "CDSL", "CAMS", "KFINTECH"]
SECTIONS = ["quarters", "profit-loss", "balance-sheet", "cash-flow", "ratios", "shareholding"]
ACCESS_DATE = "2026-10-29"


def _num(s: str):
    s = s.replace(",", "").replace("%", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse(ticker: str) -> list[dict]:
    html = (RAW / f"screener_{ticker}.html").read_text()
    soup = BeautifulSoup(html, "lxml")
    url = f"https://www.screener.in/company/{ticker}/consolidated/"
    rows: list[dict] = []
    for li in soup.select("#top-ratios li"):
        name = li.select_one(".name")
        val = li.select_one(".value")
        if name and val:
            nums = re.findall(r"[\d,]+\.?\d*", val.get_text(" ", strip=True))
            rows.append(dict(ticker=ticker, section="top-ratios", item=name.get_text(strip=True),
                             period="2026-10-29", value=_num(nums[0]) if nums else None,
                             raw=" ".join(val.get_text(" ", strip=True).split()),
                             source_url=url, access_date=ACCESS_DATE))
    for sec in SECTIONS:
        table = soup.select_one(f"section#{sec} table")
        if table is None:
            continue
        heads = [th.get_text(strip=True) for th in table.select("thead th")]
        for tr in table.select("tbody tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            item = " ".join(tds[0].get_text(" ", strip=True).replace("+", "").split())
            for h, td in zip(heads[1:], tds[1:]):
                rows.append(dict(ticker=ticker, section=sec, item=item, period=h,
                                 value=_num(td.get_text(strip=True)), raw=td.get_text(strip=True),
                                 source_url=url, access_date=ACCESS_DATE))
    return rows


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    allrows = []
    for t in TICKERS:
        allrows += parse(t)
    with open(PROCESSED / "screener_long.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
        w.writeheader()
        w.writerows(allrows)
    print(f"parse_screener: {len(allrows)} rows -> data/processed/screener_long.csv")


if __name__ == "__main__":
    main()
