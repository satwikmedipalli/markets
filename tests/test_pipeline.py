"""End-to-end on a synthetic database: a planted effect survives every check, a null one doesn't,
and the held-out run refuses to start until the method is frozen."""
import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

import pricedin.config as cfg
import pricedin.db as db

UNIVERSE = {
    "market_proxy": "SPY",
    "families": [{"id": "fomc", "kind": "fomc", "label": "test", "series": [], "rule_clarity": "clear",
                  "assets": {"SPY": None, "KRE": None, "XLP": None}}],
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    conf = tmp_path / "config"
    conf.mkdir()
    study = yaml.safe_load((cfg.CONFIG / "study.yaml").read_text())
    study["estimation"]["bootstrap_reps"] = 300
    study["validation"]["placebo_draws"] = 200
    study["validation"]["shuffle_draws"] = 200
    (conf / "study.yaml").write_text(yaml.safe_dump(study))
    (conf / "universe.yaml").write_text(yaml.safe_dump(UNIVERSE))
    shutil.copy(cfg.ROOT / "PREREGISTRATION.md", tmp_path / "PREREGISTRATION.md")
    monkeypatch.setattr(cfg, "CONFIG", conf)
    monkeypatch.setattr(cfg, "DATA", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "data" / "t.duckdb")
    import pricedin.freeze as fz
    monkeypatch.setattr(fz, "FROZEN", tmp_path / "FROZEN.json")
    monkeypatch.setattr(fz, "FILES", [conf / "study.yaml", conf / "universe.yaml"])
    cfg.study.cache_clear()
    cfg.universe.cache_clear()
    (tmp_path / "data").mkdir()
    build_db()
    yield
    cfg.study.cache_clear()
    cfg.universe.cache_clear()


def build_db():
    rng = np.random.default_rng(7)
    days = pd.bdate_range("2025-01-02", "2025-12-31")
    event_days = days[10::6][:30]                        # 30 "FOMC" days
    mins = []
    for d in days:
        open_ = pd.Timestamp(f"{d.date()} 09:31", tz="America/New_York").tz_convert("UTC")
        mins.append(pd.date_range(open_, periods=390, freq="min"))
    idx = mins[0].append(mins[1:])
    n = len(idx)
    spy_r = rng.normal(0, 0.0005, n)
    kre_r = 1.1 * spy_r + rng.normal(0, 0.0004, n)
    xlp_r = 0.5 * spy_r + rng.normal(0, 0.0004, n)
    evs, ser = [], []
    pos = pd.Series(np.arange(n), index=idx)
    for d in event_days:
        t0 = pd.Timestamp(f"{d.date()} 14:00", tz="America/New_York").tz_convert("UTC")
        labels = pd.date_range(t0 - pd.Timedelta(hours=1), t0 + pd.Timedelta(hours=1), freq="min", tz="UTC")
        dp = rng.normal(0, 0.004, len(labels))
        dp[60] += rng.choice([-1, 1]) * rng.uniform(0.05, 0.2)
        p = np.clip(0.5 + np.cumsum(dp), 0.01, 0.99)
        # KRE moves with the odds one minute AFTER the contract
        dpp = np.diff(np.r_[0.5, p])
        for j, t in enumerate(labels):
            if t in pos.index and j >= 1:
                kre_r[pos[t]] += 0.03 * dpp[j - 1]
        eid = f"fomc:{d.date()}"
        evs.append({"event_id": eid, "family": "fomc", "kind": "scheduled", "t0": t0, "label": eid,
                    "contract": "x", "in_session": True, "exclusion": None, "jump_pp": np.nan})
        ser.append(pd.DataFrame({"event_id": eid, "ts": labels, "p": p, "active": True, "two_sided": True,
                                 "spread": 0.01}))
    bars = []
    for sym, r in (("SPY", spy_r), ("KRE", kre_r), ("XLP", xlp_r)):
        bars.append(pd.DataFrame({"symbol": sym, "ts": idx, "open": 0.0, "close": 100 * np.exp(np.cumsum(r)),
                                  "volume": 1.0}))
    con = db.connect()
    db.replace_family(con, "fomc", pd.DataFrame(evs), pd.concat(ser))
    b = pd.concat(bars)
    con.register("b", b)
    con.execute("INSERT INTO bars SELECT symbol, ts, open, close, volume FROM b")
    con.close()


def test_planted_effect_found_and_null_rejected(env):
    from pricedin import analysis
    out = analysis.run(log=lambda *a: None)
    b = {r["asset"]: r for r in out["betas"]}
    ll = {r["asset"]: r for r in out["leadlag"]}
    # KRE: the effect lands at lag +1, so the contemporaneous beta is weak; lead-lag finds it
    best = max(ll["KRE"]["lags"], key=lambda r: abs(r["coef_10pp_pct"]))
    assert best["k"] == 1
    assert ll["KRE"]["verdict"] == "contract_first"
    # Dimson beta picks up the lagged effect: positive, and it survives every check
    assert b["KRE"]["beta_10pp_pct"] > 0 and b["KRE"]["survives"]
    # XLP: no planted effect -> nothing survives
    assert not b["XLP"]["survives"]
    assert ll["XLP"]["verdict"] == "same_minute_or_unclear"
    for r in b.values():                      # validation actually ran
        assert np.isfinite(r["placebo_p"]) and np.isfinite(r["shuffle_p"]) and np.isfinite(r["q_value"])
    assert out["sample"] == "train"
    assert b["KRE"]["n_events"] == 21        # 30 usable, 30% sealed


def test_holdout_needs_freeze(env):
    from pricedin import analysis, freeze
    with pytest.raises(freeze.NotFrozen):
        analysis.run(include_holdout=True, log=lambda *a: None)
    freeze.freeze("test")
    out = analysis.run(include_holdout=True, log=lambda *a: None)
    assert out["betas"][0]["n_events"] == 30
    # changing the method after the freeze blocks the held-out run again
    p = cfg.CONFIG / "study.yaml"
    p.write_text(p.read_text() + "\n# edit\n")
    with pytest.raises(freeze.NotFrozen):
        analysis.run(include_holdout=True, log=lambda *a: None)
