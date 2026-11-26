"""The estimators must recover known effects from synthetic data, and find nothing in noise."""
import numpy as np
import pandas as pd

from pricedin.analysis import Ctx, design_beta, design_leadlag, dp_vector, leadlag, returns
from pricedin.hedge import contracts, hedge
from pricedin.sources.kalshi import midquote, normalize_candle
from pricedin.stats import bh_qvalues, boot_p, bootstrap, pooled, suff

C = Ctx(pre=5, post=30, L=5)


def synth(n_events, beta, lag, rng, noise=0.0004):
    """Stock return at t = beta * dp at t - lag + market + noise."""
    units = []
    for _ in range(n_events):
        dp = rng.normal(0, 0.01, C.W + 2 * C.L)
        dp[C.L + C.pre] += 0.15                      # a jump at t0
        rm = rng.normal(0, 0.0005, C.W)
        src = dp[C.L - lag:C.L - lag + C.W]
        y = beta * src + 0.8 * rm + rng.normal(0, noise, C.W)
        units.append({"dp": dp, "y": y, "rm": rm, "rs": None, "event": {"active_share": 1.0}})
    return units


def test_beta_recovered():
    rng = np.random.default_rng(0)
    units = synth(40, 0.02, 0, rng)
    S = [suff(design_beta(u["dp"], u["rm"], None, C), u["y"]) for u in units]
    K = 2 * C.L + 1
    b = pooled(S)
    assert abs(b[:K].sum() - 0.02) < 0.003      # Dimson beta = sum over lags
    assert abs(b[K] - 0.8) < 0.05               # market control
    draws = bootstrap(S, 300, rng)[:, :K].sum(axis=1)
    assert np.percentile(draws, 2.5) < 0.02 < np.percentile(draws, 97.5)
    assert boot_p(draws) < 0.01


def test_lagged_response_counts_in_beta():
    """A stock that reacts 2 minutes after the contract still gets its full beta."""
    rng = np.random.default_rng(5)
    units = synth(40, 0.02, 2, rng)
    S = [suff(design_beta(u["dp"], u["rm"], None, C), u["y"]) for u in units]
    assert abs(pooled(S)[:2 * C.L + 1].sum() - 0.02) < 0.003


def test_no_effect_in_noise():
    rng = np.random.default_rng(1)
    units = synth(40, 0.0, 0, rng)
    S = [suff(design_beta(u["dp"], u["rm"], None, C), u["y"]) for u in units]
    draws = bootstrap(S, 500, rng)[:, :2 * C.L + 1].sum(axis=1)
    assert boot_p(draws) > 0.05


def test_leadlag_detects_contract_first():
    rng = np.random.default_rng(2)
    ll = leadlag(synth(40, 0.02, 2, rng), C, 300, rng)       # stock reacts 2 minutes after contract
    best = max(ll["lags"], key=lambda r: abs(r["coef_10pp_pct"]))
    assert best["k"] == 2
    assert ll["verdict"] == "contract_first"


def test_leadlag_detects_stocks_first():
    rng = np.random.default_rng(3)
    ll = leadlag(synth(40, 0.02, -2, rng), C, 300, rng)      # contract reacts 2 minutes after stock
    best = max(ll["lags"], key=lambda r: abs(r["coef_10pp_pct"]))
    assert best["k"] == -2
    assert ll["verdict"] == "stocks_first"


def test_leadlag_same_minute():
    rng = np.random.default_rng(4)
    ll = leadlag(synth(40, 0.02, 0, rng), C, 300, rng)
    assert ll["verdict"] == "same_minute_or_unclear"


def test_alignment_of_grids():
    """dp and returns line up on minute-END labels: a jump between minute t-1 and t shows at label t."""
    t0 = pd.Timestamp("2025-03-19 18:00", tz="UTC")
    labels = pd.date_range(t0 - pd.Timedelta(minutes=20), t0 + pd.Timedelta(minutes=40), freq="min", tz="UTC")
    p = np.where(labels >= t0, 0.6, 0.4)
    dp = dp_vector(pd.DataFrame({"ts": labels, "p": p}), t0, C)
    close = pd.Series(np.where(labels >= t0, 101.0, 100.0), index=labels)
    r = returns(close, t0, C)
    i_dp = int(np.argmax(np.abs(dp)))
    i_r = int(np.argmax(np.abs(r)))
    assert i_dp - C.L == i_r == C.pre - 1   # label t0 is window minute pre-1
    X = design_leadlag(dp, C)
    assert X[i_r, C.L] == dp[i_dp]           # k = 0 column is contemporaneous


def test_midquote_rules():
    m, two = midquote(0.4, 0.42)
    assert np.isclose(m, 0.41) and two
    assert midquote(0.0, 0.02)[0] == 0.01          # empty bid near zero: pinned
    assert np.isnan(midquote(0.0, 0.5)[0])         # empty bid mid-range: unknown
    assert np.isnan(midquote(0.3, 1.0)[0])


def test_candle_schemas():
    live = {"end_period_ts": 1793206860, "yes_bid": {"close_dollars": "0.95"}, "yes_ask": {"close_dollars": "0.96"},
            "price": {"close_dollars": "0.95"}, "volume_fp": "1000.00"}
    hist = {"end_period_ts": 1738177260, "yes_bid": {"close": "0.75"}, "yes_ask": {"close": "0.83"},
            "price": {"close": None}, "volume": "0.00"}
    a, b = normalize_candle(live), normalize_candle(hist)
    assert a["mid"] == 0.955 and a["volume"] == 1000
    assert b["mid"] == 0.79 and np.isnan(b["last"])


def test_bh():
    q = bh_qvalues(np.array([0.01, 0.04, 0.03, 0.5, np.nan]))
    # sorted p .01 .03 .04 .5 -> p*n/rank .04 .06 .0533 .5 -> step-up min .04 .0533 .0533 .5
    assert np.allclose(q[:4], [0.04, 0.16 / 3, 0.16 / 3, 0.5])
    assert np.isnan(q[4])


def test_hedge_math():
    # beta 0.5% per 10pp on $1M: $5,000 per 10pp = $500 per point = 50,000 one-cent moves
    assert np.isclose(contracts(1_000_000, 0.5), 50_000)
    h = hedge({"KRE": 1_000_000}, {"KRE": {"beta_10pp_pct": 0.5, "ci_lo": 0.2, "ci_hi": 0.8}})
    assert h["side"].startswith("buy NO") and np.isclose(h["contracts"], 50_000)
    assert np.allclose(h["range"], [20_000, 80_000])


def test_placebo_not_fooled_by_volatility():
    """No real effect, but event windows are 4x as volatile as placebo days: the t-based placebo
    must not call that significant (the raw-beta placebo did)."""
    from pricedin.stats import null_p, tstat_sum
    rng = np.random.default_rng(11)
    K = 2 * C.L + 1
    ev = synth(30, 0.0, 0, rng, noise=0.0016)                    # volatile, no effect
    S = [suff(design_beta(u["dp"], u["rm"], None, C), u["y"]) for u in ev]
    b, t = tstat_sum(S, K)
    calm_b, calm_t = [], []
    for _ in range(300):
        P = [suff(design_beta(u["dp"], u["rm"] / 4, None, C), rng.normal(0, 0.0004, C.W)) for u in ev]
        pb, pt = tstat_sum(P, K)
        calm_b.append(pb); calm_t.append(pt)
    assert null_p(t, np.array(calm_t)) > 0.05
