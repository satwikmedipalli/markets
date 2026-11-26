"""Rank candidate Kalshi contracts by traded volume (week-1 contract selection).

Selection uses volume and contract metadata only, never stock data.
"""
from __future__ import annotations

import re

import pandas as pd

from .config import DATA, ensure_dirs
from .sources.kalshi import BASE, Kalshi

KEYWORDS = re.compile(
    r"tariff|recession|shutdown|\bcpi\b|inflation|bitcoin|\bbtc\b|gdp|debt ceiling|payroll|"
    r"unemploy|trade deal|trade truce|fed chair|powell|rate cut|treasury|default|house|senate",
    re.I,
)
CATEGORIES = {"Economics", "Politics", "Financials", "Crypto", "Elections"}
SKIP_FREQ = {"fifteen_min", "hourly", "daily"}


def _all_markets(k: Kalshi, series: str) -> list[dict]:
    out = []
    for path in ("markets", "historical/markets"):
        cursor = None
        for _ in range(20):
            p = {"series_ticker": series, "limit": 1000}
            if cursor:
                p["cursor"] = cursor
            d = k.http.get(f"{BASE}/{path}", p, allow_404=True) or {}
            out += d.get("markets", [])
            cursor = d.get("cursor")
            if not cursor:
                break
    return out


def run(top: int = 60, log=print) -> pd.DataFrame:
    ensure_dirs()
    k = Kalshi()
    series = k.http.get(f"{BASE}/series", {"limit": 20000}).get("series", [])
    cands = [s for s in series if s.get("category") in CATEGORIES
             and s.get("frequency") not in SKIP_FREQ and KEYWORDS.search(s.get("title", ""))]
    log(f"[discover] {len(cands)} candidate series")
    rows = []
    for i, s in enumerate(cands):
        ms = _all_markets(k, s["ticker"])
        if not ms:
            continue
        vol = lambda m: float(m.get("volume_fp") or m.get("volume") or 0)  # noqa: E731
        best = max(ms, key=vol)
        rows.append({
            "series": s["ticker"], "category": s.get("category"), "title": s.get("title"),
            "frequency": s.get("frequency"), "n_markets": len(ms),
            "total_volume": sum(vol(m) for m in ms),
            "top_market": best["ticker"], "top_event": best.get("event_ticker"),
            "top_title": best.get("title") or best.get("yes_sub_title"),
            "top_volume": vol(best), "open_time": best.get("open_time"), "close_time": best.get("close_time"),
            "status": best.get("status"),
        })
        if i % 50 == 0:
            log(f"[discover] {i}/{len(cands)}")
    df = pd.DataFrame(rows).sort_values("top_volume", ascending=False)
    df.to_csv(DATA / "discovery.csv", index=False)
    log(df.head(top).to_string(index=False, max_colwidth=50))
    return df
