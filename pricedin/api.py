"""Read-only REST API over the exported statistics.

    uv run uvicorn pricedin.api:app --port 8300
"""
from __future__ import annotations

import json
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import WEB_DATA
from .hedge import hedge as _hedge

app = FastAPI(title="Priced In API", version="1", description=(
    "Event betas, lead-lag and market-quality statistics linking prediction-market odds to US stocks. "
    "Results describe co-movement in event windows, not causation."))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])


@lru_cache(maxsize=64)
def _read(rel: str):
    p = WEB_DATA / rel
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _need(rel: str):
    d = _read(rel)
    if d is None:
        raise HTTPException(503, f"{rel} not built yet; run the pipeline")
    return d


@app.get("/v1/meta")
def meta():
    return _need("meta.json")


@app.get("/v1/families")
def families():
    return _need("meta.json")["families"]


@app.get("/v1/families/{family}")
def family(family: str):
    d = _read(f"families/{family}.json")
    if d is None:
        raise HTTPException(404, "unknown family")
    return d


@app.get("/v1/betas")
def betas(ticker: str | None = None, family: str | None = None, survives_only: bool = False):
    rows = _need("betas.json")["betas"]
    if ticker:
        rows = [r for r in rows if r["asset"].upper() == ticker.upper()]
    if family:
        rows = [r for r in rows if r["family"] == family]
    if survives_only:
        rows = [r for r in rows if r.get("survives")]
    return rows


@app.get("/v1/leadlag/{family}")
def leadlag(family: str):
    return [r for r in _need("leadlag.json")["leadlag"] if r["family"] == family]


@app.get("/v1/quality/{family}")
def quality(family: str):
    d = _read(f"families/{family}.json")
    if d is None:
        raise HTTPException(404, "unknown family")
    keys = ("event_id", "t0", "usable", "exclusion", "active_share", "median_spread_pp", "split")
    return [{k: e[k] for k in keys} for e in d["events"]]


class HedgeIn(BaseModel):
    family: str
    positions: dict[str, float]


@app.post("/v1/hedge")
def hedge(body: HedgeIn):
    rows = {r["asset"]: r for r in _need("betas.json")["betas"] if r["family"] == body.family}
    if not rows:
        raise HTTPException(404, "no betas for that family")
    return _hedge(body.positions, rows)
