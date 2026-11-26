"""Small HTTP helper: retries with backoff and an on-disk cache for immutable responses."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import httpx

from ..config import CACHE


class Http:
    def __init__(self, name: str, headers: dict | None = None, min_interval: float = 0.08):
        self.client = httpx.Client(timeout=40, headers={"User-Agent": "pricedin-research/0.1", **(headers or {})})
        self.cache_dir = CACHE / name
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self._last = 0.0

    def _key(self, url: str, params: dict | None) -> Path:
        raw = url + "?" + json.dumps(params or {}, sort_keys=True)
        return self.cache_dir / (hashlib.sha256(raw.encode()).hexdigest()[:32] + ".json")

    def get(self, url: str, params: dict | None = None, cache: bool = False, allow_404: bool = False):
        path = self._key(url, params)
        if cache and path.exists():
            return json.loads(path.read_text())
        for attempt in range(6):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.client.get(url, params=params)
            except httpx.TransportError:
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 404 and allow_404:
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(30, 2 ** attempt))
                continue
            r.raise_for_status()
            data = r.json()
            if cache:
                path.write_text(json.dumps(data))
            return data
        raise RuntimeError(f"GET {url} failed after retries")
