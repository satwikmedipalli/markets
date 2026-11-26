"""Alpaca minute bars (free plan: full SIP history as long as the data is >15 minutes old)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ..config import alpaca_keys
from .http import Http

BASE = "https://data.alpaca.markets/v2/stocks/bars"


class Alpaca:
    def __init__(self):
        keys = alpaca_keys()
        if not keys:
            raise RuntimeError(
                "Alpaca keys missing. Copy .env.example to .env and set ALPACA_KEY / ALPACA_SECRET."
            )
        self.http = Http(
            "alpaca",
            headers={"APCA-API-KEY-ID": keys[0], "APCA-API-SECRET-KEY": keys[1]},
            min_interval=0.31,  # free plan: 200 requests/minute
        )

    def bars(self, symbols: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        """1-minute bars labelled by the minute's END time (UTC), matching the contract grid."""
        rows, token = [], None
        while True:
            p = {
                "symbols": ",".join(sorted(symbols)),
                "timeframe": "1Min",
                "start": start.isoformat().replace("+00:00", "Z"),
                "end": end.isoformat().replace("+00:00", "Z"),
                "limit": 10000,
                "adjustment": "all",
                "feed": "sip",
            }
            if token:
                p["page_token"] = token
            d = self.http.get(BASE, p, cache=True)
            for sym, bars in (d.get("bars") or {}).items():
                for b in bars:
                    rows.append((sym, b["t"], b["o"], b["c"], b["v"]))
            token = d.get("next_page_token")
            if not token:
                break
        df = pd.DataFrame(rows, columns=["symbol", "t", "open", "close", "volume"])
        if df.empty:
            return df.assign(ts=pd.Series(dtype="datetime64[ns, UTC]"))
        # Alpaca stamps a bar with its START; shift to END so both markets share a clock.
        df["ts"] = pd.to_datetime(df["t"], utc=True) + pd.Timedelta(minutes=1)
        return df.drop(columns="t")
