"""Polymarket public data: Gamma API for market metadata, CLOB prices-history for prices.

prices-history returns the market's mid/price points, not a book, so Polymarket contracts
have no spread measure. Their quality score uses print frequency only, and the methods page
says so. Run `pricedin audit` first: if resolved markets only return coarse points, they fail
the quality filter and are excluded automatically.
"""
from __future__ import annotations

import json
import time as _time
from datetime import datetime

import pandas as pd

from .http import Http

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
CHUNK_SECONDS = 7 * 24 * 3600


class Polymarket:
    def __init__(self):
        self.http = Http("polymarket")

    def market(self, slug: str) -> dict | None:
        d = self.http.get(f"{GAMMA}/markets", {"slug": slug}, cache=True)
        return d[0] if d else None

    def yes_token(self, slug: str) -> str | None:
        m = self.market(slug)
        if not m:
            return None
        outcomes = json.loads(m.get("outcomes") or "[]")
        tokens = json.loads(m.get("clobTokenIds") or "[]")
        for o, t in zip(outcomes, tokens):
            if str(o).lower() == "yes":
                return t
        return tokens[0] if tokens else None

    def prices(self, token_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Price points bucketed to 1-minute bars labelled by the minute's END time (UTC)."""
        s, e = int(start.timestamp()), int(end.timestamp())
        now = _time.time()
        pts = []
        while s < e:
            ce = min(e, s + CHUNK_SECONDS)
            d = self.http.get(
                f"{CLOB}/prices-history",
                {"market": token_id, "startTs": s, "endTs": ce, "fidelity": 1},
                cache=ce < now - 2 * 86400,
            )
            pts += d.get("history", [])
            s = ce
        if not pts:
            return pd.DataFrame(columns=["ts", "bid", "ask", "mid", "two_sided", "last", "volume"])
        df = pd.DataFrame(pts).rename(columns={"t": "t", "p": "mid"})
        df["ts"] = pd.to_datetime(df["t"], unit="s", utc=True).dt.floor("min") + pd.Timedelta(minutes=1)
        df = df.groupby("ts", as_index=False)["mid"].last()
        df["bid"] = float("nan")
        df["ask"] = float("nan")
        df["two_sided"] = True
        df["last"] = df["mid"]
        df["volume"] = float("nan")
        return df[["ts", "bid", "ask", "mid", "two_sided", "last", "volume"]]
