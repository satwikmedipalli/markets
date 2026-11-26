"""Kalshi vs. CME FedWatch at daily resolution.

FedWatch has no free intraday history, so this comparison is daily and secondary. Put daily
FedWatch probabilities in data/fedwatch.csv (columns: date, meeting, p_cut, with meeting as
YYYY-MM-DD and p_cut in 0-1); see data/fedwatch.example.csv. Kalshi's daily P(cut) for the same
meeting is built from daily candles of that meeting's cut outcomes (closing midquotes).
"""
from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pandas as pd

from .config import DATA, universe
from .events import fomc_meetings
from .sources.kalshi import Kalshi, normalize_candle, BASE


def kalshi_daily(k: Kalshi, series: str, tickers: list[str], start, end) -> pd.Series:
    total = None
    for tk in tickers:
        d = k.http.get(f"{BASE}/series/{series}/markets/{tk}/candlesticks",
                       {"start_ts": int(start.timestamp()), "end_ts": int(end.timestamp()), "period_interval": 1440},
                       allow_404=True)
        if d is None:
            d = k.http.get(f"{BASE}/historical/markets/{tk}/candlesticks",
                           {"start_ts": int(start.timestamp()), "end_ts": int(end.timestamp()), "period_interval": 1440},
                           allow_404=True) or {}
        rows = [normalize_candle(c) for c in d.get("candlesticks", [])]
        if not rows:
            continue
        s = pd.DataFrame(rows).set_index("ts")["mid"]
        s.index = (s.index - pd.Timedelta(minutes=1)).tz_convert("America/New_York").date
        total = s if total is None else total.add(s, fill_value=0)
    return total if total is not None else pd.Series(dtype=float)


def run(log=print) -> dict:
    path = DATA / "fedwatch.csv"
    if not path.exists():
        raise RuntimeError(f"Add daily FedWatch data to {path} (see data/fedwatch.example.csv).")
    fw = pd.read_csv(path, parse_dates=["date", "meeting"], comment="#")
    k = Kalshi()
    fam = next(f for f in universe()["families"] if f["kind"] == "fomc")
    meetings = fomc_meetings(k, fam["series"]).set_index("day")
    rows = []
    for mday, g in fw.groupby(fw["meeting"].dt.date):
        if mday not in meetings.index:
            log(f"[fedwatch] no Kalshi event for meeting {mday}")
            continue
        m = meetings.loc[mday]
        start = pd.Timestamp(g["date"].min(), tz="America/New_York") - timedelta(days=1)
        end = pd.Timestamp(g["date"].max(), tz="America/New_York") + timedelta(days=2)
        ks = kalshi_daily(k, m["series"], m["cut_tickers"], start, end)
        for _, r in g.iterrows():
            kv = ks.get(r["date"].date(), np.nan)
            rows.append({"meeting": mday, "date": r["date"].date(), "fedwatch": r["p_cut"], "kalshi": kv})
    df = pd.DataFrame(rows).dropna()
    if df.empty:
        raise RuntimeError("No overlapping days between FedWatch and Kalshi.")
    df["gap_pp"] = (df["kalshi"] - df["fedwatch"]) * 100
    d = df.sort_values(["meeting", "date"]).groupby("meeting")
    chg = pd.DataFrame({"dk": d["kalshi"].diff(), "df": d["fedwatch"].diff()}).dropna()
    out = {
        "days": int(len(df)), "meetings": int(df["meeting"].nunique()),
        "mean_gap_pp": float(df["gap_pp"].mean()), "mean_abs_gap_pp": float(df["gap_pp"].abs().mean()),
        "level_corr": float(df["kalshi"].corr(df["fedwatch"])),
        "daily_change_corr": float(chg["dk"].corr(chg["df"])) if len(chg) > 2 else None,
        "rows": json.loads(df.to_json(orient="records", date_format="iso")),
    }
    (DATA / "fedwatch_comparison.json").write_text(json.dumps(out, indent=2))
    log(f"[fedwatch] {out['days']} days, {out['meetings']} meetings: mean |gap| {out['mean_abs_gap_pp']:.1f} pts, "
        f"level corr {out['level_corr']:.2f}, daily-change corr {out['daily_change_corr']}")
    return out
