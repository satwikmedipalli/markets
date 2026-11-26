"""Paths, settings and time helpers shared across the pipeline."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
CACHE = DATA / "cache"
DB_PATH = DATA / "pricedin.duckdb"
FROZEN = ROOT / "FROZEN.json"
WEB_DATA = ROOT / "web" / "public" / "data"

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

load_dotenv(ROOT / ".env")


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


@lru_cache
def study() -> dict:
    return yaml.safe_load((CONFIG / "study.yaml").read_text())


@lru_cache
def universe() -> dict:
    return yaml.safe_load((CONFIG / "universe.yaml").read_text())


@dataclass(frozen=True)
class Session:
    open: time
    close: time
    pre_min: int
    post_min: int


def session() -> Session:
    s = study()
    return Session(
        open=_hhmm(s["session"]["open"]),
        close=_hhmm(s["session"]["close"]),
        pre_min=int(s["window"]["pre_min"]),
        post_min=int(s["window"]["post_min"]),
    )


def alpaca_keys() -> tuple[str, str] | None:
    k, s = os.getenv("ALPACA_KEY", "").strip(), os.getenv("ALPACA_SECRET", "").strip()
    return (k, s) if k and s else None


def ensure_dirs() -> None:
    for p in (DATA, CACHE):
        p.mkdir(parents=True, exist_ok=True)
