"""Estimators built on per-event sufficient statistics.

Each event contributes X'X and X'y after demeaning within the event (event fixed effects).
Pooled OLS is then (sum X'X)^-1 (sum X'y), and every resampling scheme (event bootstrap,
placebo days, shuffled pairs) is a re-weighting or re-pairing of these small matrices.
"""
from __future__ import annotations

import numpy as np


def suff(X: np.ndarray, y: np.ndarray) -> tuple:
    """(X'X, X'y, y'y, n) after demeaning within the event."""
    Xd = X - X.mean(axis=0, keepdims=True)
    yd = y - y.mean()
    return Xd.T @ Xd, Xd.T @ yd, float(yd @ yd), len(y)


def tstat_sum(stats, K: int) -> tuple[float, float]:
    """Pooled OLS; return (sum of the first K coefficients, its conventional t-statistic).

    The t-statistic does not depend on the scale of y, so it can be compared across windows of
    different volatility (event vs. placebo days). Event fixed effects cost one dof per event.
    """
    A = sum(s[0] for s in stats)
    b = sum(s[1] for s in stats)
    yy = sum(s[2] for s in stats)
    n = sum(s[3] for s in stats)
    coef = solve(A, b)
    dof = max(n - len(stats) - A.shape[0], 1)
    s2 = max(yy - coef @ b, 0.0) / dof
    Ainv = np.linalg.pinv(A)
    one = np.zeros(A.shape[0])
    one[:K] = 1.0
    se = np.sqrt(s2 * one @ Ainv @ one)
    est = float(coef[:K].sum())
    return est, (est / se if se > 0 else 0.0)


def solve(XtX: np.ndarray, Xty: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(XtX, Xty, rcond=None)[0]


def pooled(stats: list[tuple[np.ndarray, np.ndarray]], w: np.ndarray | None = None) -> np.ndarray:
    A = np.stack([s[0] for s in stats])
    b = np.stack([s[1] for s in stats])
    if w is None:
        w = np.ones(len(stats))
    return solve(np.tensordot(w, A, 1), np.tensordot(w, b, 1))


def bootstrap(stats, reps: int, rng: np.random.Generator) -> np.ndarray:
    """Event (cluster) bootstrap: resample whole events with replacement."""
    n = len(stats)
    A = np.stack([s[0] for s in stats])
    b = np.stack([s[1] for s in stats])
    W = rng.multinomial(n, np.full(n, 1 / n), size=reps).astype(float)
    out = np.empty((reps, A.shape[1]))
    for i in range(reps):
        out[i] = solve(np.tensordot(W[i], A, 1), np.tensordot(W[i], b, 1))
    return out


def boot_p(draws: np.ndarray) -> float:
    """Two-sided bootstrap p-value for H0: coefficient = 0 (percentile method)."""
    n = len(draws)
    lo = (np.sum(draws <= 0) + 1) / (n + 1)
    hi = (np.sum(draws >= 0) + 1) / (n + 1)
    return float(min(1.0, 2 * min(lo, hi)))


def null_p(observed: float, null: np.ndarray) -> float:
    null = null[np.isfinite(null)]
    if len(null) == 0:
        return float("nan")
    return float((1 + np.sum(np.abs(null) >= abs(observed))) / (1 + len(null)))


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg q-values; NaNs pass through."""
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    pv = p[ok]
    if len(pv) == 0:
        return q
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    res = np.empty_like(pv)
    res[order] = np.clip(ranked, 0, 1)
    q[ok] = res
    return q


def derangement(n: int, rng: np.random.Generator) -> np.ndarray:
    while True:
        p = rng.permutation(n)
        if not np.any(p == np.arange(n)):
            return p
