"""Hedge calculator: contracts that offset a portfolio's exposure to an event.

A $1 binary contract gains $0.01 per probability point. If the portfolio moves by beta (return
per unit probability), its dollar change per point is V * beta / 100, so

    contracts = V * beta / 100 / 0.01 = V * beta

Positive beta (portfolio gains as the event gets likelier): buy NO, or sell YES.
"""
from __future__ import annotations


def contracts(position_value: float, beta_10pp_pct: float) -> float:
    beta = beta_10pp_pct / 10  # % per 10 points -> return (fraction) per unit probability
    return position_value * beta


def hedge(positions: dict[str, float], betas: dict[str, dict]) -> dict:
    """positions: ticker -> dollar value (negative = short). betas: ticker -> beta row."""
    total = lo = hi = 0.0
    lines, missing = [], []
    for tk, v in positions.items():
        b = betas.get(tk)
        if not b:
            missing.append(tk)
            continue
        c = contracts(v, b["beta_10pp_pct"])
        cl, ch = sorted((contracts(v, b["ci_lo"]), contracts(v, b["ci_hi"])))
        total, lo, hi = total + c, lo + cl, hi + ch
        lines.append({"ticker": tk, "value": v, "beta_10pp_pct": b["beta_10pp_pct"], "contracts": c})
    side = "buy NO (or sell YES)" if total > 0 else "buy YES" if total < 0 else "none"
    return {
        "contracts": abs(total), "side": side, "range": sorted((abs(lo), abs(hi))) if lo * hi > 0 else [0.0, max(abs(lo), abs(hi))],
        "lines": lines, "missing": missing,
        "note": "Offsets co-movement measured in event windows, not a guarantee. Range from the beta's 95% interval.",
    }
