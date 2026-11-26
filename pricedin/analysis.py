"""Modules 1 and 2 plus validation: event betas, who moves first, placebos, shuffles, q-values.

Conventions
- Minute labels are minute END times (UTC) for both markets.
- Window returns cover (t0 - pre, t0 + post]: W = pre + post one-minute log returns.
- dp is the one-minute change in probability (0-1 scale). Betas are reported per 10 points, in %.
- Event beta = Dimson sum of dp coefficients at lags -L..+L (with market/sector controls).
- Lead-lag coefficient at lag k: stock return at minute t on dp at minute t - k.
  k > 0  -> the contract moved first.   k < 0 -> stocks moved first.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import db
from .config import study, universe
from .freeze import assert_frozen
from .quality import score
from .stats import bh_qvalues, boot_p, bootstrap, derangement, null_p, pooled, suff, tstat_sum


@dataclass
class Ctx:
    pre: int
    post: int
    L: int

    @property
    def W(self) -> int:
        return self.pre + self.post


def ctx() -> Ctx:
    s = study()
    return Ctx(s["window"]["pre_min"], s["window"]["post_min"], s["estimation"]["leadlag_max_lag"])


# ------------------------------------------------------------------ data access
def dp_vector(series: pd.DataFrame, t0: pd.Timestamp, c: Ctx) -> np.ndarray | None:
    """dp at labels t0-pre+1-L ... t0+post+L  (length W + 2L)."""
    labels = pd.date_range(t0 - pd.Timedelta(minutes=c.pre + c.L), t0 + pd.Timedelta(minutes=c.post + c.L),
                           freq="min", tz="UTC")
    p = series.set_index("ts")["p"].reindex(labels).ffill()
    if p.isna().any():
        return None
    return np.diff(p.to_numpy())


def returns(close: pd.Series | None, t: pd.Timestamp, c: Ctx) -> np.ndarray | None:
    """Log returns at labels t-pre+1 ... t+post (length W). Requires a bar near every label."""
    if close is None or close.empty:
        return None
    labels = pd.date_range(t - pd.Timedelta(minutes=c.pre), t + pd.Timedelta(minutes=c.post), freq="min", tz="UTC")
    idx = close.index.get_indexer(labels, method="ffill", tolerance=pd.Timedelta(minutes=5))
    if (idx < 0).any():
        return None
    v = close.to_numpy()[idx]
    return np.diff(np.log(v))


class Data:
    def __init__(self, include_holdout: bool = False):
        con = db.connect()
        self.q = score(con)
        self.series = dict(tuple(con.execute("SELECT * FROM event_series ORDER BY ts").df().groupby("event_id")))
        bars = con.execute("SELECT symbol, ts, close FROM bars ORDER BY ts").df()
        con.close()
        self.close = {s: g.set_index("ts")["close"] for s, g in bars.groupby("symbol")}
        splits = ["train", "holdout"] if include_holdout else ["train"]
        self.usable = self.q[self.q["usable"] & self.q["split"].isin(splits)]
        self.c = ctx()
        from .bars import plan  # deterministic placebo days
        try:
            con = db.connect()
            p = plan(con)
            con.close()
            self.placebo = {e: g["t"].tolist() for e, g in p[p["kind"] == "placebo"].groupby("event_id")}
        except Exception:
            self.placebo = {}

    def R(self, sym: str | None, t: pd.Timestamp):
        return returns(self.close.get(sym), t, self.c) if sym else None


# --------------------------------------------------------------------- design
def design_beta(dp: np.ndarray, rm, rs, c: Ctx) -> np.ndarray:
    """Dimson (1979) design: dp at every lag -L..+L, then market and sector controls.
    The event beta is the SUM of the dp coefficients, so a response that lands a minute
    early or late (non-synchronous quotes, minute boundaries) still counts."""
    cols = [design_leadlag(dp, c)]
    if rm is not None:
        cols.append(rm)
    if rs is not None:
        cols.append(rs)
    return np.column_stack(cols)


def design_leadlag(dp: np.ndarray, c: Ctx) -> np.ndarray:
    # column j corresponds to lag k = L - j ... ordered k = +L .. -L ; we reorder to k = -L..+L
    cols = {}
    for k in range(-c.L, c.L + 1):
        cols[k] = dp[c.L - k:c.L - k + c.W]
    return np.column_stack([cols[k] for k in range(-c.L, c.L + 1)])


@dataclass
class Spec:
    family: str
    asset: str
    sector: str | None
    market: str | None


def specs() -> list[Spec]:
    mkt = universe().get("market_proxy", "SPY")
    out = []
    for f in universe()["families"]:
        for a, sec in f["assets"].items():
            out.append(Spec(f["id"], a, sec if a != mkt else None, None if a == mkt else mkt))
    return out


# ------------------------------------------------------------------- estimate
def estimate(d: Data, sp: Spec, reps: int, rng) -> tuple[dict | None, dict | None, list]:
    c = d.c
    ev = d.usable[d.usable["family"] == sp.family].sort_values("t0")
    units = []  # per event: dp, returns
    for _, e in ev.iterrows():
        dp = dp_vector(d.series.get(e["event_id"], pd.DataFrame(columns=["ts", "p"])), e["t0"], c)
        y = d.R(sp.asset, e["t0"])
        rm = d.R(sp.market, e["t0"]) if sp.market else None
        rs = d.R(sp.sector, e["t0"]) if sp.sector else None
        if dp is None or y is None or (sp.market and rm is None) or (sp.sector and rs is None):
            continue
        units.append({"event": e, "dp": dp, "y": y, "rm": rm, "rs": rs})
    if len(units) < 5:
        return None, None, units

    # ---- module 1: event beta with controls (primary) and raw
    K = 2 * c.L + 1                        # dp lag columns; beta = their sum
    S = [suff(design_beta(u["dp"], u["rm"], u["rs"], c), u["y"]) for u in units]
    b, t_obs = tstat_sum(S, K)
    draws = bootstrap(S, reps, rng)[:, :K].sum(axis=1)
    Sraw = [suff(design_leadlag(u["dp"], c), u["y"]) for u in units]
    braw = pooled(Sraw).sum()
    draws_raw = bootstrap(Sraw, reps, rng).sum(axis=1)

    # placebo: same dp, stock-side data from a placebo day at the same clock time
    nd = int(study()["validation"]["placebo_draws"])
    pool = []
    for u in units:
        opts = []
        for t in d.placebo.get(u["event"]["event_id"], []):
            y = d.R(sp.asset, t)
            rm = d.R(sp.market, t) if sp.market else None
            rs = d.R(sp.sector, t) if sp.sector else None
            if y is None or (sp.market and rm is None) or (sp.sector and rs is None):
                continue
            opts.append(suff(design_beta(u["dp"], rm, rs, c), y))
        pool.append(opts)
    placebo = np.full(nd, np.nan)
    if all(pool):
        for i in range(nd):
            placebo[i] = tstat_sum([o[rng.integers(len(o))] for o in pool], K)[1]

    # shuffled pairs: dp from event e, stock-side data from a different event
    ns = int(study()["validation"]["shuffle_draws"])
    n = len(units)
    cache: dict[tuple[int, int], tuple] = {}
    shuffle = np.full(ns, np.nan)
    for i in range(ns):
        perm = derangement(n, rng)
        st = []
        for a, bb in enumerate(perm):
            key = (a, int(bb))
            if key not in cache:
                v = units[bb]
                cache[key] = suff(design_beta(units[a]["dp"], v["rm"], v["rs"], c), v["y"])
            st.append(cache[key])
        shuffle[i] = tstat_sum(st, K)[1]

    beta = {
        "family": sp.family, "asset": sp.asset,
        "controls": [x for x in (sp.market, sp.sector) if x],
        "n_events": n, "n_obs": n * c.W,
        "beta_10pp_pct": 10 * b, "ci_lo": 10 * np.percentile(draws, 2.5), "ci_hi": 10 * np.percentile(draws, 97.5),
        "p_boot": boot_p(draws),
        "raw_beta_10pp_pct": 10 * braw, "raw_ci_lo": 10 * np.percentile(draws_raw, 2.5),
        "raw_ci_hi": 10 * np.percentile(draws_raw, 97.5), "raw_p_boot": boot_p(draws_raw),
        # placebo and shuffle compare t-statistics: scale-free, so calm placebo days can't
        # make volatile event windows look significant
        "t_stat": t_obs, "placebo_p": null_p(t_obs, placebo), "shuffle_p": null_p(t_obs, shuffle),
    }

    # ---- module 2: who moves first (raw returns: controls would absorb macro timing)
    ll = leadlag(units, c, reps, rng)
    act = study()["quality"]["robustness_active_share"]
    hi_units = [u for u in units if u["event"]["active_share"] >= act]
    ll["robust_high_activity"] = leadlag(hi_units, c, reps, rng) if len(hi_units) >= 5 else None
    ll.update({"family": sp.family, "asset": sp.asset})
    return beta, ll, units


def leadlag(units, c: Ctx, reps: int, rng) -> dict:
    S = [suff(design_leadlag(u["dp"], c), u["y"]) for u in units]
    coef = pooled(S)
    draws = bootstrap(S, reps, rng)
    ks = list(range(-c.L, c.L + 1))
    lead_idx = [ks.index(k) for k in ks if k > 0]
    lag_idx = [ks.index(k) for k in ks if k < 0]
    total = draws.sum(axis=1)
    sign = np.sign(coef.sum()) or 1.0
    D = sign * (draws[:, lead_idx].sum(axis=1) - draws[:, lag_idx].sum(axis=1))
    d_hat = sign * (coef[lead_idx].sum() - coef[lag_idx].sum())
    lo, hi = np.percentile(D, [2.5, 97.5])
    # provisional verdict from the interval; run() downgrades it unless the BH q-value passes too
    verdict = "contract_first" if lo > 0 else "stocks_first" if hi < 0 else "same_minute_or_unclear"
    return {
        "n_events": len(units),
        "lags": [{"k": k, "coef_10pp_pct": 10 * coef[i], "ci_lo": 10 * np.percentile(draws[:, i], 2.5),
                  "ci_hi": 10 * np.percentile(draws[:, i], 97.5)} for i, k in enumerate(ks)],
        "total_10pp_pct": 10 * coef.sum(),
        "total_ci": [10 * np.percentile(total, 2.5), 10 * np.percentile(total, 97.5)],
        "lead_minus_lag_10pp_pct": 10 * d_hat, "lead_minus_lag_ci": [10 * lo, 10 * hi],
        "verdict": verdict, "p_boot": boot_p(D),
    }


# ------------------------------------------------------------------------ run
def run(include_holdout: bool = False, log=print) -> dict:
    if include_holdout:
        assert_frozen()
    s = study()
    rng = np.random.default_rng(int(s["estimation"]["seed"]) + (1 if include_holdout else 0))
    reps = int(s["estimation"]["bootstrap_reps"])
    d = Data(include_holdout)
    if d.usable.empty:
        raise RuntimeError("No usable events. Run `pricedin ingest` first.")
    if not d.close:
        raise RuntimeError("No stock bars. Add Alpaca keys to .env and run `pricedin bars`.")
    betas, lls, examples = [], [], {}
    for sp in specs():
        b, ll, units = estimate(d, sp, reps, rng)
        if b is None:
            log(f"[run] {sp.family} {sp.asset}: fewer than 5 events with data, skipped")
            continue
        betas.append(b)
        lls.append(ll)
        log(f"[run] {sp.family:<20} {sp.asset:<5} beta/10pp {b['beta_10pp_pct']:+.3f}% "
            f"[{b['ci_lo']:+.3f}, {b['ci_hi']:+.3f}]  placebo p {b['placebo_p']:.3f}  lead-lag {ll['verdict']}")
        examples.setdefault(sp.family, {})[sp.asset] = [
            {"event_id": u["event"]["event_id"], "cum_ret_pct": (np.cumsum(u["y"]) * 100).round(4).tolist()}
            for u in units]
    bt = pd.DataFrame(betas)
    alpha = float(s["validation"]["fdr_q"])
    bt["q_value"] = bh_qvalues(bt["p_boot"].to_numpy())
    bt["survives"] = (bt["q_value"] < alpha) & (bt["placebo_p"] < alpha) & (bt["shuffle_p"] < alpha)
    # lead-lag gets the same multiple-testing correction as the betas
    llq = bh_qvalues(np.array([r["p_boot"] for r in lls]))
    for r, qv in zip(lls, llq):
        r["q_value"] = float(qv)
        r["uncorrected_verdict"] = r["verdict"]
        if not qv < alpha:
            r["verdict"] = "same_minute_or_unclear"
    out = {
        "sample": "train+holdout" if include_holdout else "train",
        "betas": json.loads(bt.to_json(orient="records")),
        "leadlag": json.loads(pd.Series(lls).to_json(orient="values")),
        "paths": examples,
    }
    return out
