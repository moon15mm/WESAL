"""Fixed-window rate limiting backed by Redis (falls back to in-process memory)."""
from __future__ import annotations

import logging
import threading
import time

import redis

from app.core.config import settings
from app.core.errors import RateLimited

log = logging.getLogger("wesal.ratelimit")


class _MemoryStore:
    def __init__(self):
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, window: int) -> int:
        now = time.time()
        with self._lock:
            count, reset = self._data.get(key, (0, now + window))
            if now > reset:
                count, reset = 0, now + window
            count += 1
            self._data[key] = (count, reset)
            return count

    def clear(self):
        with self._lock:
            self._data.clear()


_memory = _MemoryStore()
_redis: redis.Redis | None = None


def _client() -> redis.Redis | None:
    global _redis
    if settings.rate_limit_backend != "redis":
        return None
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
    return _redis


def hit(key: str, limit: int, window_seconds: int) -> None:
    if not settings.rate_limit_enabled:
        return
    full_key = f"rl:{key}:{int(time.time() // window_seconds)}"
    count: int
    client = _client()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.incr(full_key)
            pipe.expire(full_key, window_seconds + 1)
            count = int(pipe.execute()[0])
        except redis.RedisError:
            log.warning("redis unavailable for rate limiting; using memory store")
            count = _memory.hit(full_key, window_seconds)
    else:
        count = _memory.hit(full_key, window_seconds)
    if count > limit:
        raise RateLimited(params={"retry_after": window_seconds})


def reset_memory() -> None:
    _memory.clear()
