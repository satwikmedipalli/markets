"""Seal the method before touching held-out events.

`pricedin freeze` records a SHA-256 of the study config, the contract universe, the
pre-registration and every analysis source file. The held-out run refuses to start unless
all of them still match, so the method cannot quietly change after the held-out test.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from .config import CONFIG, FROZEN, ROOT

FILES = [
    CONFIG / "study.yaml",
    CONFIG / "universe.yaml",
    ROOT / "PREREGISTRATION.md",
    *sorted((ROOT / "pricedin").glob("*.py")),
    *sorted((ROOT / "pricedin" / "sources").glob("*.py")),
]
SKIP = {"export.py", "api.py", "mcp_server.py", "cli.py", "audit.py", "hedge.py", "discover.py", "fedwatch.py"}


def digest() -> dict[str, str]:
    out = {}
    for f in FILES:
        if f.name in SKIP or not f.exists():
            continue
        key = str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else f.name
        out[key] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def freeze(note: str = "") -> dict:
    rec = {"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": note, "files": digest()}
    FROZEN.write_text(json.dumps(rec, indent=2) + "\n")
    return rec


class NotFrozen(RuntimeError):
    pass


def assert_frozen() -> None:
    if not FROZEN.exists():
        raise NotFrozen("Held-out events are sealed. Run `pricedin freeze` first.")
    rec = json.loads(FROZEN.read_text())
    now = digest()
    changed = sorted(k for k in set(rec["files"]) | set(now) if rec["files"].get(k) != now.get(k))
    if changed:
        raise NotFrozen("Method changed since freeze: " + ", ".join(changed) +
                        ". Log the change in PREREGISTRATION.md and re-freeze before the held-out run.")
