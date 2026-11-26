"""Put sparse contract quotes on a regular 1-minute clock (labels = minute END, UTC)."""
from __future__ import annotations

from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd

from .config import ET, session


def minute_index(start, end) -> pd.DatetimeIndex:
    return pd.date_range(pd.Timestamp(start).ceil("min"), pd.Timestamp(end).floor("min"), freq="min", tz="UTC")


def to_grid(q: pd.DataFrame, start, end) -> pd.DataFrame:
    """Forward-fill the last known quote onto every minute in [start, end].

    `active` marks minutes where the venue reported something; forward-filled minutes are stale.
    Quotes before `start` seed the fill, so callers should fetch some lookback.
    """
    idx = minute_index(start, end)
    if q.empty:
        return pd.DataFrame({"ts": idx, "p": np.nan, "active": False, "two_sided": False, "spread": np.nan})
    q = q.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    q = q[q.index <= idx[-1]]
    active = pd.Series(idx.isin(q.index), index=idx)
    full = q.reindex(q.index.union(idx)).sort_index()
    mid = full["mid"].ffill()
    spread = (full["ask"] - full["bid"]).ffill()
    two = full["two_sided"].astype("float").ffill()
    out = pd.DataFrame({
        "ts": idx,
        "p": mid.reindex(idx).to_numpy(),
        "active": active.to_numpy(),
        "two_sided": two.reindex(idx).fillna(0).astype(bool).to_numpy(),
        "spread": spread.reindex(idx).to_numpy(),
    })
    return out


def combine(grids: list[pd.DataFrame]) -> pd.DataFrame:
    """Sum mutually exclusive outcomes (e.g. all 'cut' markets) into one probability.

    The sum is undefined at any minute where an outcome has no price (never silently zero).
    Book quality (spread, two-sidedness) comes from the DOMINANT outcome, the one with the highest
    average probability: tail outcomes pinned near 0 routinely have no bid, which says nothing about
    whether the probability that matters is well quoted. (Changed 2026-11-26, before stock data.)
    """
    base = grids[0][["ts"]].copy()
    P = np.vstack([g["p"].to_numpy() for g in grids])
    base["p"] = P.sum(axis=0)  # NaN if any outcome is NaN
    base["active"] = np.any([g["active"].to_numpy() for g in grids], axis=0)
    dom = grids[int(np.nanargmax([np.nanmean(g["p"]) if g["p"].notna().any() else -1 for g in grids]))]
    base["two_sided"] = dom["two_sided"].to_numpy()
    base["spread"] = dom["spread"].to_numpy()
    return base


def session_check(t0: pd.Timestamp) -> tuple[bool, str | None]:
    """Is the whole [t0 - pre, t0 + post] window inside the regular session on a weekday?"""
    s = session()
    local = t0.tz_convert(ET)
    if local.weekday() >= 5:
        return False, "weekend"
    day = local.date()
    open_ = datetime.combine(day, s.open, tzinfo=ET)
    close = datetime.combine(day, s.close, tzinfo=ET)
    if local - timedelta(minutes=s.pre_min) < open_:
        return False, "before_open" if local < open_ else "window_crosses_open"
    if local + timedelta(minutes=s.post_min) > close:
        return False, "after_close" if local >= close else "window_crosses_close"
    return True, None


def et_time(day, hhmm: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(day, hhmm, tzinfo=ET)).tz_convert("UTC")
