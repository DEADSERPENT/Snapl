"""
Two-tier cache: Redis when available, in-process dict as fallback.

The redirect path is read-heavy (many GETs per POST), so caching the
short_code -> long_url mapping avoids a DB round-trip on every click.
TTL prevents serving stale entries after a link is deleted/expired.
"""

import time
from typing import Optional
from app.config import REDIS_URL, CACHE_TTL_SECONDS


class _InMemoryCache:
    def __init__(self, ttl: int):
        self._store: dict[str, tuple[str, float]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


def _build_cache():
    if REDIS_URL:
        try:
            import redis
            client = redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()

            class _RedisCache:
                def get(self, key: str) -> Optional[str]:
                    return client.get(f"snapl:{key}")

                def set(self, key: str, value: str) -> None:
                    client.setex(f"snapl:{key}", CACHE_TTL_SECONDS, value)

                def delete(self, key: str) -> None:
                    client.delete(f"snapl:{key}")

                def clear(self) -> None:
                    for k in client.scan_iter("snapl:*"):
                        client.delete(k)

            return _RedisCache()
        except Exception:
            pass  # fall through to in-memory

    return _InMemoryCache(ttl=CACHE_TTL_SECONDS)


cache = _build_cache()
