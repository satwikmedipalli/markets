"""Week-1 data audit: how many usable events exist, and why the rest are excluded.

Uses contract data only. The decision gate (min usable training events) is evaluated here.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import db
from .config import DATA, study, universe
from .quality import score


def run(log=print) -> dict:
    con = db.connect()
    q = score(con)
    nbars = con.execute("SELECT count(*) FROM bars").fetchone()[0]
    con.close()
    if q.empty:
        raise RuntimeError("No events. Run `pricedin ingest` first.")
    fams = {f["id"]: f for f in universe()["families"]}
    rows = []
    for fam, g in q.groupby("family"):
        u = g[g["usable"]]
        rows.append({
            "family": fam,
            "label": fams.get(fam, {}).get("label", fam),
            "type": fams.get(fam, {}).get("type"),
            "kind": g["kind"].iloc[0],
            "rule_clarity": fams.get(fam, {}).get("rule_clarity"),
            "events": len(g),
            "in_session": int(g["in_session"].sum()),
            "usable": len(u),
            "train": int((u["split"] == "train").sum()),
            "holdout": int((u["split"] == "holdout").sum()),
            "median_spread_pp": float(np.nanmedian(u["median_spread_pp"])) if len(u) and u["median_spread_pp"].notna().any() else None,
            "median_active_share": float(u["active_share"].median()) if len(u) else None,
            "exclusions": {k: int(v) for k, v in g["exclusion"].fillna("usable").value_counts().items()},
            "first": g["t0"].min().isoformat(), "last": g["t0"].max().isoformat(),
        })
    fam_df = pd.DataFrame(rows).sort_values("usable", ascending=False)
    gate = int(study()["decision_gate"]["min_usable_events"])
    n_train = int(fam_df["train"].sum())
    n_out = int((~q["in_session"]).sum())
    report = {
        "families": json.loads(fam_df.to_json(orient="records")),
        "totals": {
            "events": int(len(q)), "in_session": int(q["in_session"].sum()), "outside_session": n_out,
            "usable": int(q["usable"].sum()), "train": n_train, "holdout": int(fam_df["holdout"].sum()),
            "stock_bars": int(nbars),
        },
        "gate": {"min_usable_train_events": gate, "train_events": n_train, "pass": n_train >= gate},
        "exclusions": {k: int(v) for k, v in q["exclusion"].fillna("usable").value_counts().items()},
    }
    (DATA / "audit.json").write_text(json.dumps(report, indent=2, default=str))
    log(fam_df[["family", "events", "in_session", "usable", "train", "holdout", "median_spread_pp",
                "median_active_share"]].to_string(index=False))
    log(f"\nexclusions: {report['exclusions']}")
    log(f"gate: {n_train} usable training events (need {gate}) -> {'PASS' if report['gate']['pass'] else 'WIDEN THE CONTRACT SET'}")
    return report
