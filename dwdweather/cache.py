from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, cast

from platformdirs import user_cache_dir

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
APP_NAME = "dwdweather"


def cache_dir() -> Path:
    return Path(user_cache_dir(APP_NAME))


def cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return cache_dir() / f"{namespace}_{digest}.json"


def get_cached(namespace: str, key: str) -> dict[str, Any] | None:
    path = cache_path(namespace, key)
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        if time.time() < entry["expires"]:
            return cast(dict[str, Any], entry["data"])
        path.unlink(missing_ok=True)
    except (OSError, KeyError, json.JSONDecodeError, TypeError):
        return None
    return None


def set_cached(namespace: str, key: str, data: dict[str, Any], ttl: int = CACHE_TTL_SECONDS) -> None:
    path = cache_path(namespace, key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"expires": time.time() + ttl, "data": data}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return
