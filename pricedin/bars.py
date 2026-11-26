"""Load stock minute bars for every usable event window and its placebo days."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from . import db
from .config import study, universe
from .grid import et_time
from .quality import score, window_bounds
from .sources.alpaca import Alpaca

PAD = timedelta(minutes=3)


def family_symbols(fam: dict) -> list[str]:
    syms = set(fam["assets"]) | {universe().get("market_proxy", "SPY")}
    syms |= {s for s in fam["assets"].values() if s}
    return sorted(syms)


def placebo_days(t0: pd.Timestamp, n: int, rng: np.random.Generator) -> list[pd.Timestamp]:
    """Same clock time on weekdays 5-60 trading days away (either side), never on another event day."""
    lo, hi = study()["validation"]["placebo_day_offset"]
    days = pd.bdate_range(t0.normalize() - pd.Timedelta(days=int(hi * 1.6)), t0.normalize() + pd.Timedelta(days=int(hi * 1.6)))
    ref = t0.tz_convert("America/New_York").date()
    last_ok = (pd.Timestamp.now(tz="America/New_York") - pd.Timedelta(days=1)).date()  # no future/same-day data
    pos = [d for d in days if lo <= abs(np.busday_count(ref, d.date())) <= hi and d.date() <= last_ok]
    pick = rng.choice(len(pos), size=min(n, len(pos)), replace=False)
    local = t0.tz_convert("America/New_York")
    return [et_time(pos[i].date(), local.time()) for i in sorted(pick)]


def plan(con) -> pd.DataFrame:
    """Every (family, event, kind, t0) window that needs bars. Deterministic given the seed."""
    q = score(con)
    q = q[q["usable"]]
    pool = int(study()["validation"].get("placebo_pool", 20))
    rng = np.random.default_rng(int(study()["estimation"]["seed"]))
    event_days = set(q["t0"].dt.tz_convert("America/New_York").dt.date)
    rows = []
    for _, e in q.sort_values(["family", "t0"]).iterrows():
        rows.append({"family": e["family"], "event_id": e["event_id"], "kind": "event", "t": e["t0"]})
        for t in placebo_days(e["t0"], pool + 5, rng):
            if t.tz_convert("America/New_York").date() in event_days:
                continue
            rows.append({"family": e["family"], "event_id": e["event_id"], "kind": "placebo", "t": t})
    p = pd.DataFrame(rows)
    # keep `pool` placebo days per event
    p["rank"] = p.groupby(["event_id", "kind"]).cumcount()
    return p[(p["kind"] == "event") | (p["rank"] < pool)].drop(columns="rank")


def load(log=print) -> None:
    con = db.connect()
    fams = {f["id"]: f for f in universe()["families"]}
    todo = plan(con)
    a = Alpaca()
    n = len(todo)
    for i, r in enumerate(todo.itertuples()):
        syms = family_symbols(fams[r.family])
        s, e = window_bounds(r.t)
        start, end = s - PAD - pd.Timedelta(minutes=1), e + PAD
        try:
            df = a.bars(syms, start.to_pydatetime(), end.to_pydatetime())
        except Exception as ex:  # one bad window must not stop the load
            log(f"[bars] skipped {r.event_id} {r.kind} {r.t:%Y-%m-%d %H:%M}: {str(ex)[:80]}")
            continue
        if not df.empty:
            con.register("nb", df[["symbol", "ts", "open", "close", "volume"]])
            con.execute("""INSERT INTO bars SELECT * FROM nb
                           WHERE NOT EXISTS (SELECT 1 FROM bars b WHERE b.symbol = nb.symbol AND b.ts = nb.ts)""")
            con.unregister("nb")
        if i % 100 == 0:
            log(f"[bars] {i}/{n} windows")
    log(f"[bars] done: {con.execute('SELECT count(*) FROM bars').fetchone()[0]:,} bars stored")
    con.close()
