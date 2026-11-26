"""Kalshi public market data.

Notes verified against the live API (2026-11-26):
- Markets settled before the historical cutoff are served under /historical/...
  with an older schema (`close` instead of `close_dollars`, `volume` instead of `volume_fp`).
- 1-minute candlesticks carry yes_bid / yes_ask OHLC, so a true midquote is available.
- Candles only exist for minutes with activity; gaps mean "nothing happened", not missing data.
- Fed decision contracts close 1-5 minutes BEFORE the 2:00pm ET statement, so the event
  study uses the NEXT meeting's contract, which trades through the statement.
"""
from __future__ import annotations

import math
import time as _time
from datetime import datetime, timezone

import pandas as pd

from .http import Http

BASE = "https://api.elections.kalshi.com/trade-api/v2"
CHUNK_SECONDS = 3 * 24 * 3600  # 4,320 one-minute candles per request at most


def _f(x) -> float:
    if x is None or x == "":
        return math.nan
    return float(x)


def _pick(obj: dict | None, key: str) -> float:
    if not obj:
        return math.nan
    return _f(obj.get(f"{key}_dollars", obj.get(key)))


def midquote(bid: float, ask: float) -> tuple[float, bool]:
    """Return (mid, two_sided). A side priced 0 (bid) or 1 (ask) means that side is empty."""
    has_bid = not math.isnan(bid) and bid > 0
    has_ask = not math.isnan(ask) and ask < 1
    if has_bid and has_ask:
        return (bid + ask) / 2, True
    # One-sided books at the extremes still pin the probability tightly.
    if has_ask and not has_bid and ask <= 0.03:
        return ask / 2, False
    if has_bid and not has_ask and bid >= 0.97:
        return (1 + bid) / 2, False
    return math.nan, False


def normalize_candle(c: dict) -> dict:
    bid = _pick(c.get("yes_bid"), "close")
    ask = _pick(c.get("yes_ask"), "close")
    mid, two = midquote(bid, ask)
    return {
        "ts": pd.Timestamp(c["end_period_ts"], unit="s", tz="UTC"),
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "two_sided": two,
        "last": _pick(c.get("price"), "close"),
        "volume": _f(c.get("volume_fp", c.get("volume"))),
    }


class Kalshi:
    def __init__(self):
        self.http = Http("kalshi")

    # ---- metadata -------------------------------------------------------
    def series(self, ticker: str) -> dict | None:
        d = self.http.get(f"{BASE}/series/{ticker}", cache=True, allow_404=True)
        return d.get("series") if d else None

    def events(self, series_ticker: str, status: str | None = None) -> list[dict]:
        out, cursor = [], None
        while True:
            p = {"series_ticker": series_ticker, "limit": 200}
            if status:
                p["status"] = status
            if cursor:
                p["cursor"] = cursor
            d = self.http.get(f"{BASE}/events", p)
            out += d.get("events", [])
            cursor = d.get("cursor")
            if not cursor:
                return out

    def markets(self, event_ticker: str) -> list[dict]:
        d = self.http.get(f"{BASE}/markets", {"event_ticker": event_ticker, "limit": 200})
        ms = d.get("markets", [])
        if ms:
            return ms
        d = self.http.get(f"{BASE}/historical/markets", {"event_ticker": event_ticker, "limit": 200}, cache=True)
        return d.get("markets", [])

    def open_markets(self, max_pages: int = 60) -> list[dict]:
        out, cursor = [], None
        for _ in range(max_pages):
            p = {"status": "open", "limit": 1000, "mve_filter": "exclude"}
            if cursor:
                p["cursor"] = cursor
            d = self.http.get(f"{BASE}/markets", p)
            out += d.get("markets", [])
            cursor = d.get("cursor")
            if not cursor:
                break
        return out

    # ---- prices ---------------------------------------------------------
    def candles(self, series_ticker: str, market_ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
        """1-minute candles in [start, end], labelled by the minute's END time (UTC)."""
        s, e = int(start.timestamp()), int(end.timestamp())
        now = _time.time()
        rows = []
        while s < e:
            ce = min(e, s + CHUNK_SECONDS)
            params = {"start_ts": s, "end_ts": ce, "period_interval": 1}
            immutable = ce < now - 2 * 86400
            d = self.http.get(
                f"{BASE}/series/{series_ticker}/markets/{market_ticker}/candlesticks",
                params, cache=immutable, allow_404=True,
            )
            if d is None:
                d = self.http.get(
                    f"{BASE}/historical/markets/{market_ticker}/candlesticks",
                    params, cache=immutable, allow_404=True,
                ) or {}
            rows += [normalize_candle(c) for c in d.get("candlesticks", [])]
            s = ce
        if not rows:
            return pd.DataFrame(columns=["ts", "bid", "ask", "mid", "two_sided", "last", "volume"])
        df = pd.DataFrame(rows).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        return df


def parse_time(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
