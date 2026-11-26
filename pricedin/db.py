"""DuckDB store. Small, local, rebuilt from cached API responses at any time."""
from __future__ import annotations

import duckdb
import pandas as pd

from .config import DB_PATH, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    family      TEXT,      -- e.g. fomc, kalshi:KXRECSSNBER-26
    kind        TEXT,      -- scheduled | unscheduled
    t0          TIMESTAMPTZ,
    label       TEXT,
    contract    TEXT,      -- what the probability series is
    in_session  BOOLEAN,
    exclusion   TEXT,      -- null when usable on session grounds
    jump_pp     DOUBLE     -- size of the 5-min move that defined it (unscheduled), else null
);
CREATE TABLE IF NOT EXISTS event_series (
    event_id   TEXT,
    ts         TIMESTAMPTZ,  -- minute END, UTC
    p          DOUBLE,       -- probability (0-1)
    active     BOOLEAN,      -- a candle / print exists in this minute
    two_sided  BOOLEAN,
    spread     DOUBLE        -- ask - bid (probability units), null for Polymarket
);
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT,
    ts     TIMESTAMPTZ,      -- minute END, UTC
    open   DOUBLE,
    close  DOUBLE,
    volume DOUBLE
);
CREATE TABLE IF NOT EXISTS bar_days (symbol TEXT, day DATE);
"""


def connect() -> duckdb.DuckDBPyConnection:
    ensure_dirs()
    con = duckdb.connect(str(DB_PATH))
    con.execute("SET TimeZone='UTC'")
    con.execute(SCHEMA)
    return con


def replace_family(con, family: str, events: pd.DataFrame, series: pd.DataFrame) -> None:
    ids = con.execute("SELECT event_id FROM events WHERE family = ?", [family]).df()["event_id"].tolist()
    if ids:
        con.execute("DELETE FROM event_series WHERE event_id IN (SELECT unnest(?))", [ids])
        con.execute("DELETE FROM events WHERE family = ?", [family])
    if not events.empty:
        cols = ["event_id", "family", "kind", "t0", "label", "contract", "in_session", "exclusion", "jump_pp"]
        con.register("ev", events[cols])
        con.execute("INSERT INTO events SELECT * FROM ev")
        con.unregister("ev")
    if not series.empty:
        cols = ["event_id", "ts", "p", "active", "two_sided", "spread"]
        con.register("es", series[cols])
        con.execute("INSERT INTO event_series SELECT * FROM es")
        con.unregister("es")
