"""Write the site / API data files (computed statistics only, never raw venue feeds)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import db
from .config import DATA, WEB_DATA, study, universe
from .quality import score, window_bounds


def _load(name: str):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else None


def _clean(o):
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), default=str, separators=(",", ":")))


def run(log=print) -> None:
    con = db.connect()
    q = score(con)
    se = con.execute("SELECT event_id, ts, p FROM event_series ORDER BY ts").df()
    con.close()
    audit = _load("audit.json")
    train = _load("results_train.json")
    hold = _load("results_holdout.json")
    s = study()
    series = dict(tuple(se.groupby("event_id")))
    fams = universe()["families"]

    status = "results" if train else "awaiting_stock_data"
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "holdout_unsealed": bool(hold),
        "window": s["window"], "quality": s["quality"], "jump": s["jump"],
        "validation": s["validation"], "gate": s["decision_gate"],
        "audit": audit,
        "families": [{k: f.get(k) for k in ("id", "label", "type", "kind", "rule_clarity", "rule_note", "question")}
                     | {"assets": list(f["assets"]), "contract": f.get("market") or "next-meeting cut outcomes"}
                     for f in fams],
    }
    _write(WEB_DATA / "meta.json", meta)

    for f in fams:
        g = q[q["family"] == f["id"]].sort_values("t0")
        evs = []
        for _, e in g.iterrows():
            a, b = window_bounds(e["t0"])
            ser = series.get(e["event_id"])
            path = None
            if ser is not None and e["usable"]:
                w = ser[(ser["ts"] >= a) & (ser["ts"] <= b)]
                path = [{"m": int((t - e["t0"]).total_seconds() // 60), "p": round(float(p) * 100, 2)}
                        for t, p in zip(w["ts"], w["p"]) if pd.notna(p)]
            evs.append({
                "event_id": e["event_id"], "t0": e["t0"].isoformat(), "label": e["label"],
                "usable": bool(e["usable"]), "exclusion": e["exclusion"], "split": e["split"],
                "in_session": bool(e["in_session"]),
                "active_share": e["active_share"], "median_spread_pp": e["median_spread_pp"],
                "p_start": e["p_start"], "dp_window_pp": e["dp_window_pp"], "jump_pp": e["jump_pp"],
                "path": path,
            })
        out = {"family": f["id"], "events": evs}
        if train:
            out["betas"] = [r for r in train["betas"] if r["family"] == f["id"]]
            out["leadlag"] = [r for r in train["leadlag"] if r["family"] == f["id"]]
            out["paths"] = train.get("paths", {}).get(f["id"], {})
        if hold:
            out["holdout_betas"] = [r for r in hold["betas"] if r["family"] == f["id"]]
            out["holdout_leadlag"] = [r for r in hold["leadlag"] if r["family"] == f["id"]]
        _write(WEB_DATA / "families" / f"{f['id']}.json", out)

    if train:
        _write(WEB_DATA / "betas.json", {"sample": "train", "betas": train["betas"]})
        _write(WEB_DATA / "leadlag.json", {"sample": "train", "leadlag": [
            {k: v for k, v in r.items()} for r in train["leadlag"]]})
    if hold:
        _write(WEB_DATA / "holdout.json", hold)
    log(f"[export] wrote {WEB_DATA} (status: {status})")
