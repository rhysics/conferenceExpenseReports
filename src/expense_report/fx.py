"""Historical FX rates via the Frankfurter API (https://frankfurter.dev).

Frankfurter serves ECB reference rates and is free, key-less, and actively
maintained — a more reliable alternative to the abandoned forex-python.
Results are cached on disk so repeated runs/currencies don't re-hit the
network, and report generation can be repeated offline afterwards.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

import requests

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{date}"
MAX_FALLBACK_DAYS = 7
REQUEST_TIMEOUT = 10


class FxError(RuntimeError):
    pass


class FxCache:
    """A small on-disk JSON cache keyed by (date, base currency, target currencies)."""

    def __init__(self, path: Path):
        self.path = path
        self._data: dict[str, dict] = {}
        if path.is_file():
            try:
                self._data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def get(self, key: str) -> dict | None:
        return self._data.get(key)

    def set(self, key: str, value: dict) -> None:
        self._data[key] = value
        try:
            self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            pass


def _cache_key(d: date, base: str, targets: Sequence[str]) -> str:
    sorted_targets = ",".join(sorted(t.upper() for t in targets))
    return f"{d.isoformat()}|{base}|{sorted_targets}"


def get_rates(purchase_date: date, base: str, targets: Sequence[str], cache: FxCache) -> tuple[dict[str, float], date]:
    """Return ({currency_code: rate, ...}, actual_date_used).

    The returned dict always includes an entry for `base` itself (1.0) plus
    every currency in `targets`. If Frankfurter has no rate for
    `purchase_date` (e.g. a weekend/bank holiday), earlier dates are tried
    (up to MAX_FALLBACK_DAYS) and the date actually used is returned so the
    caller can surface that fallback to the user.
    """
    base = base.upper()
    targets = [t.upper() for t in targets]
    symbols = [c for c in targets if c != base]

    cache_key = _cache_key(purchase_date, base, targets)
    cached = cache.get(cache_key)
    if cached is not None:
        rates = dict(cached["rates"])
        rates[base] = 1.0
        return rates, date.fromisoformat(cached["date"])

    if not symbols:
        return {base: 1.0}, purchase_date

    d = purchase_date
    last_error: Exception | None = None
    for _ in range(MAX_FALLBACK_DAYS + 1):
        try:
            response = requests.get(
                FRANKFURTER_URL.format(date=d.isoformat()),
                params={"base": base, "symbols": ",".join(symbols)},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            rates = payload.get("rates") or {}
            if rates:
                cache.set(cache_key, {"date": d.isoformat(), "rates": rates})
                full_rates = dict(rates)
                full_rates[base] = 1.0
                return full_rates, d
        except requests.RequestException as exc:
            last_error = exc
        d -= timedelta(days=1)

    raise FxError(
        f"could not obtain an FX rate for {base} on or before {purchase_date.isoformat()}"
        + (f" ({last_error})" if last_error else "")
    )
