"""MCP server: lets an AI assistant query Priced In.

Claude Code:  claude mcp add pricedin -- uv --directory ~/pricedin run python -m pricedin.mcp_server
"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from .config import WEB_DATA
from .hedge import hedge as _hedge

mcp = MCPServer("pricedin")

CAVEAT = "Co-movement in event windows (stocks move WITH the odds), not causation."


def _read(rel: str):
    p = WEB_DATA / rel
    return json.loads(p.read_text()) if p.exists() else None


@mcp.tool()
def list_events() -> dict:
    """List the event families (prediction-market contracts) Priced In covers, with sample sizes."""
    m = _read("meta.json") or {}
    audit = {f["family"]: f for f in (m.get("audit") or {}).get("families", [])}
    return {"status": m.get("status"), "families": [
        {**f, "usable_events": audit.get(f["id"], {}).get("usable")} for f in m.get("families", [])]}


@mcp.tool()
def get_event_betas(ticker: str) -> dict:
    """Event betas for a stock or ETF: % move per 10-point change in each event's odds, with 95% CIs,
    placebo/shuffle p-values, q-value, and whether the result survives all checks."""
    d = _read("betas.json")
    if not d:
        return {"error": "results not built yet"}
    rows = [r for r in d["betas"] if r["asset"].upper() == ticker.upper()]
    return {"ticker": ticker.upper(), "betas": rows, "caveat": CAVEAT,
            "note": "If the ticker isn't covered, use a covered ETF proxy (e.g. XLF or KRE for banks)."}


@mcp.tool()
def lead_lag(event: str) -> dict:
    """Who moves first for an event family: per-minute lead-lag coefficients and a verdict
    (contract_first, stocks_first, same_minute_or_unclear)."""
    d = _read("leadlag.json")
    if not d:
        return {"error": "results not built yet"}
    return {"event": event, "results": [r for r in d["leadlag"] if r["family"] == event], "caveat": CAVEAT}


@mcp.tool()
def hedge(portfolio: dict[str, float], event: str) -> dict:
    """Number of event contracts that offsets a portfolio's exposure. portfolio = {ticker: dollar value}."""
    d = _read("betas.json")
    if not d:
        return {"error": "results not built yet"}
    rows = {r["asset"]: r for r in d["betas"] if r["family"] == event}
    return _hedge(portfolio, rows) | {"event": event}


if __name__ == "__main__":
    mcp.run()
