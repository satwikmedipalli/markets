"""Build event lists and their probability series.

Scheduled (FOMC): t0 = 2:00pm ET on each decision day. The probability is P(cut at the NEXT
meeting), the sum of midquotes of that meeting's "cut" outcomes (tickers ending -C25, -C26, -C>25).

Unscheduled: t0 = start of a 5-minute midquote move larger than a threshold set from the
contract's own history (study.yaml `jump`). Stock data is never touched here.
"""
from __future__ import annotations

import warnings
from datetime import timedelta

import numpy as np
import pandas as pd

from . import db
from .config import ET, study, universe
from .grid import combine, et_time, to_grid
from .grid import session_check as _session_check
from .sources.kalshi import Kalshi, parse_time
from .sources.polymarket import Polymarket

warnings.filterwarnings("ignore", message="All-NaN slice encountered")

LOOKBACK = timedelta(hours=24)   # quotes before the window, to seed the forward fill
PAD = timedelta(minutes=20)      # extra minutes either side for lags


def _window(t0: pd.Timestamp):
    s = study()
    lag = int(s["estimation"]["leadlag_max_lag"])
    start = t0 - timedelta(minutes=s["window"]["pre_min"] + lag) - PAD
    end = t0 + timedelta(minutes=s["window"]["post_min"] + lag) + PAD
    return start, end


# ---------------------------------------------------------------------------- FOMC
def fomc_meetings(k: Kalshi, series_list: list[str]) -> pd.DataFrame:
    rows = []
    for series in series_list:
        for ev in k.events(series):
            ms = k.markets(ev["event_ticker"])
            if not ms:
                continue
            close = min(parse_time(m["close_time"]) for m in ms if m.get("close_time"))
            decision_day = close.astimezone(ET).date()
            cut = [m["ticker"] for m in ms if m["ticker"].rsplit("-", 1)[-1].startswith("C")]
            rows.append({
                "series": series, "event_ticker": ev["event_ticker"], "day": decision_day,
                "close": close, "cut_tickers": cut, "settled": ev.get("status") in (None, "settled", "finalized")
                and close < pd.Timestamp.now(tz="UTC"),
            })
    df = pd.DataFrame(rows).sort_values("day").drop_duplicates("day", keep="last").reset_index(drop=True)
    return df


def build_fomc(k: Kalshi, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    meetings = fomc_meetings(k, cfg["series"])
    stmt = _hhmm(study()["fomc"]["statement_time"])
    evs, ser = [], []
    for i in range(len(meetings) - 1):
        m, nxt = meetings.iloc[i], meetings.iloc[i + 1]
        if m["close"] > pd.Timestamp.now(tz="UTC"):
            break  # meeting has not happened yet
        t0 = et_time(m["day"], stmt)
        ok, why = _session_check(t0)
        eid = f"fomc:{m['day']:%Y-%m-%d}"
        start, end = _window(t0)
        grids = []
        for tk in nxt["cut_tickers"]:
            q = k.candles(nxt["series"], tk, start - LOOKBACK, end)
            grids.append(to_grid(q, start, end))
        if not grids:
            why = why or "no_next_meeting_contracts"
            g = to_grid(pd.DataFrame(), start, end)
        else:
            g = combine(grids)
        g["event_id"] = eid
        ser.append(g)
        evs.append({
            "event_id": eid, "family": "fomc", "kind": "scheduled", "t0": t0,
            "label": f"FOMC {m['day']:%b %-d, %Y}: P(cut) at {nxt['event_ticker']}",
            "contract": f"sum of cut outcomes, {nxt['event_ticker']}",
            "in_session": ok, "exclusion": why, "jump_pp": np.nan,
        })
    return pd.DataFrame(evs), (pd.concat(ser) if ser else pd.DataFrame())


# ------------------------------------------------------------------- unscheduled
def detect_jumps(g: pd.DataFrame, horizon: int, q: float, min_abs: float, dedupe: int) -> pd.DataFrame:
    """Return jump start times. g is a full-life minute grid with column p."""
    p = g.set_index("ts")["p"]
    d = (p - p.shift(horizon)).abs()
    valid = d.dropna()
    if valid.empty:
        return pd.DataFrame(columns=["t0", "jump"])
    thr = max(min_abs, float(valid.quantile(q)))
    hits = valid[valid >= thr]
    out, last = [], None
    for t, v in hits.items():
        if last is not None and t - last < pd.Timedelta(minutes=dedupe):
            continue
        last = t
        out.append({"t0": t - pd.Timedelta(minutes=horizon), "jump": float(v), "threshold": thr})
    return pd.DataFrame(out)


def contract_history(src: str, cfg: dict, k: Kalshi, pm: Polymarket):
    if src == "kalshi":
        ms = k.markets(cfg["event_ticker"]) if cfg.get("event_ticker") else []
        m = next((x for x in ms if x["ticker"] == cfg["market"]), None)
        if m is None:
            raise ValueError(f"market {cfg['market']} not found")
        start = parse_time(m.get("open_time")) or parse_time(m["close_time"]) - timedelta(days=365)
        end = min(parse_time(m["close_time"]), pd.Timestamp.now(tz="UTC").to_pydatetime())
        q = k.candles(cfg["series"], cfg["market"], start, end)
        return q, start, end
    if src == "polymarket":
        tok = pm.yes_token(cfg["slug"])
        m = pm.market(cfg["slug"])
        start = parse_time(m.get("startDate")) or parse_time(m.get("createdAt"))
        end = min(parse_time(m.get("endDate")) or pd.Timestamp.now(tz="UTC").to_pydatetime(),
                  pd.Timestamp.now(tz="UTC").to_pydatetime())
        q = pm.prices(tok, start, end)
        return q, start, end
    raise ValueError(src)


def build_unscheduled(fam: dict, k: Kalshi, pm: Polymarket) -> tuple[pd.DataFrame, pd.DataFrame]:
    j = study()["jump"]
    q, start, end = contract_history(fam["source"], fam, k, pm)
    if q.empty:
        return pd.DataFrame(), pd.DataFrame()
    life = to_grid(q, q["ts"].min(), q["ts"].max())
    jumps = detect_jumps(life, int(j["horizon_min"]), float(j["quantile"]),
                         float(j["min_abs_pp"]) / 100, int(j["dedupe_min"]))
    evs, ser = [], []
    for _, r in jumps.iterrows():
        t0 = pd.Timestamp(r["t0"]).floor("min")
        ok, why = _session_check(t0)
        eid = f"{fam['id']}:{t0:%Y-%m-%dT%H:%M}"
        ws, we = _window(t0)
        g = to_grid(q, ws, we)
        g["event_id"] = eid
        ser.append(g)
        evs.append({
            "event_id": eid, "family": fam["id"], "kind": "unscheduled", "t0": t0,
            "label": f"{fam['label']}: {r['jump'] * 100:.0f}-point move",
            "contract": fam.get("market") or fam.get("slug"),
            "in_session": ok, "exclusion": why, "jump_pp": r["jump"] * 100,
        })
    return pd.DataFrame(evs), (pd.concat(ser) if ser else pd.DataFrame())


def _hhmm(s: str):
    from datetime import time
    h, m = s.split(":")
    return time(int(h), int(m))


def ingest(only: str | None = None, log=print) -> None:
    k, pm = Kalshi(), Polymarket()
    con = db.connect()
    for fam in universe()["families"]:
        if only and fam["id"] != only:
            continue
        log(f"[ingest] {fam['id']} ...")
        try:
            if fam["kind"] == "fomc":
                ev, se = build_fomc(k, fam)
            else:
                ev, se = build_unscheduled(fam, k, pm)
        except Exception as e:  # keep going; the audit reports missing families
            log(f"[ingest] {fam['id']} FAILED: {e}")
            continue
        db.replace_family(con, fam["id"], ev, se)
        n_ok = int(ev["in_session"].sum()) if not ev.empty else 0
        log(f"[ingest] {fam['id']}: {len(ev)} events, {n_ok} inside the session")
    con.close()
