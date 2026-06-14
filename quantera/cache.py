"""Small file-based JSON TTL cache."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from quantera import config


def cache_get(key: str) -> dict[str, Any] | None:
    path = _path_for_key(key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored_at = datetime.fromisoformat(payload["stored_at"])
        ttl = int(payload["ttl"])
        if datetime.now(timezone.utc) > stored_at + timedelta(seconds=ttl):
            return None
        value = payload["value"]
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def cache_set(key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "key": key,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "ttl": int(ttl_seconds),
        "value": value,
    }
    path = _path_for_key(key)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _cache_dir() -> Path:
    return Path(config.CACHE_DIR)


def _path_for_key(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    readable = "".join(char if char.isalnum() else "_" for char in key)[:60]
    return _cache_dir() / f"{readable}-{digest}.json"
