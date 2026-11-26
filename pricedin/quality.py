"""Module 3: market quality per event window, and the train / held-out split."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import db
from .config import study, universe


def window_bounds(t0: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    s = study()["window"]
    return t0 - pd.Timedelta(minutes=s["pre_min"]), t0 + pd.Timedelta(minutes=s["post_min"])


def score(con=None) -> pd.DataFrame:
    """One row per event: activity, spread, two-sidedness, pass/fail with a reason, and split."""
    own = con is None
    con = con or db.connect()
    ev = con.execute("SELECT * FROM events ORDER BY family, t0").df()
    se = con.execute("SELECT * FROM event_series").df()
    if own:
        con.close()
    if ev.empty:
        return ev
    q = study()["quality"]
    fams = {f["id"]: f for f in universe()["families"]}
    se = se.sort_values("ts")
    groups = dict(tuple(se.groupby("event_id")))
    rows = []
    for _, e in ev.iterrows():
        g = groups.get(e["event_id"], pd.DataFrame(columns=se.columns))
        a, b = window_bounds(e["t0"])
        w = g[(g["ts"] > a) & (g["ts"] <= b)]
        n = max(len(w), 1)
        p0 = g.loc[g["ts"] <= a, "p"].dropna()
        p1 = w["p"].dropna()
        spread_pp = float(np.nanmedian(w["spread"])) * 100 if w["spread"].notna().any() else np.nan
        r = {
            "event_id": e["event_id"],
            "active_minutes": int(w["active"].sum()),
            "active_share": float(w["active"].sum()) / n,
            "two_sided_share": float(w["two_sided"].sum()) / n,
            "median_spread_pp": spread_pp,
            "p_start": float(p0.iloc[-1]) if len(p0) else np.nan,
            "p_end": float(p1.iloc[-1]) if len(p1) else np.nan,
            "rule_clarity": fams.get(e["family"], {}).get("rule_clarity", "clear"),
        }
        r["dp_window_pp"] = (r["p_end"] - r["p_start"]) * 100
        reason = e["exclusion"]
        if reason is None or (isinstance(reason, float) and np.isnan(reason)):
            reason = None
            if np.isnan(r["p_start"]) or w["p"].isna().any():
                reason = "no_price"
            elif not np.isnan(spread_pp) and spread_pp > q["max_median_spread_pp"]:
                reason = "wide_spread"
            elif r["two_sided_share"] < q["min_two_sided_share"] and not np.isnan(spread_pp):
                reason = "one_sided_book"
            elif r["active_minutes"] < q["min_active_minutes"]:
                reason = "inactive"
        r["exclusion"] = reason
        r["usable"] = reason is None
        rows.append(r)
    out = ev.drop(columns=["exclusion"]).merge(pd.DataFrame(rows), on="event_id")
    return assign_split(out)


def assign_split(df: pd.DataFrame) -> pd.DataFrame:
    """Most recent `holdout_share` of USABLE events in each family are sealed (by date only)."""
    share = float(study()["validation"]["holdout_share"])
    df = df.copy()
    df["split"] = None
    for fam, g in df[df["usable"]].groupby("family"):
        g = g.sort_values("t0")
        n_hold = int(np.floor(len(g) * share))
        hold = g.index[len(g) - n_hold:] if n_hold else []
        df.loc[g.index, "split"] = "train"
        df.loc[hold, "split"] = "holdout"
    return df
