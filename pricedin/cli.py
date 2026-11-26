"""pricedin <command>

  discover   rank candidate Kalshi contracts by volume            (no keys)
  ingest     build events + probability series from Kalshi/Poly    (no keys)
  audit      week-1 audit and decision gate                       (no keys)
  bars       load stock minute bars for event + placebo windows    (Alpaca keys)
  run        modules 1-2 + validation on the TRAINING events
  freeze     seal the method (hash of config + analysis code)
  holdout    one-time run including the sealed held-out events (requires freeze)
  fedwatch   daily Kalshi vs. CME FedWatch comparison (needs data/fedwatch.csv)
  export     write web/public/data for the site and API
  all        ingest -> audit -> bars -> run -> export
"""
from __future__ import annotations

import argparse
import json
import sys

from .config import DATA


def _save(name, obj):
    (DATA / name).write_text(json.dumps(obj, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pricedin", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["discover", "ingest", "audit", "bars", "run", "freeze", "holdout", "fedwatch", "export", "all"])
    ap.add_argument("--family", help="ingest one family only")
    ap.add_argument("--note", default="", help="freeze note")
    a = ap.parse_args(argv)

    if a.command == "discover":
        from . import discover
        discover.run()
    elif a.command == "ingest":
        from . import events
        events.ingest(a.family)
    elif a.command == "audit":
        from . import audit
        audit.run()
    elif a.command == "bars":
        from . import bars
        bars.load()
    elif a.command == "run":
        from . import analysis
        _save("results_train.json", analysis.run())
    elif a.command == "freeze":
        from . import freeze
        rec = freeze.freeze(a.note)
        print(f"frozen {len(rec['files'])} files at {rec['frozen_at']}")
    elif a.command == "holdout":
        from . import analysis
        _save("results_holdout.json", analysis.run(include_holdout=True))
    elif a.command == "fedwatch":
        from . import fedwatch
        fedwatch.run()
    elif a.command == "export":
        from . import export
        export.run()
    elif a.command == "all":
        from . import analysis, audit, bars, events, export
        events.ingest()
        audit.run()
        bars.load()
        _save("results_train.json", analysis.run())
        export.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
