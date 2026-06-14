from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from quantera import cache, config


def test_cache_set_get_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    cache.cache_set("financials:AAPL", {"ticker": "AAPL"}, ttl_seconds=60)

    assert cache.cache_get("financials:AAPL") == {"ticker": "AAPL"}


def test_expired_entry_is_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    key = "financials:AAPL"
    path = cache._path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "key": key,
                "stored_at": (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat(),
                "ttl": 60,
                "value": {"ticker": "AAPL"},
            }
        ),
        encoding="utf-8",
    )

    assert cache.cache_get(key) is None


def test_corrupt_file_is_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    key = "prices:AAPL:504"
    path = cache._path_for_key(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert cache.cache_get(key) is None


def test_namespaced_keys_do_not_collide(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    cache.cache_set("financials:AAPL", {"kind": "financials"}, ttl_seconds=60)
    cache.cache_set("prices:AAPL:504", {"kind": "prices"}, ttl_seconds=60)

    assert cache.cache_get("financials:AAPL") == {"kind": "financials"}
    assert cache.cache_get("prices:AAPL:504") == {"kind": "prices"}
