"""缓存抽象层：配置了 Redis 就用 Redis，否则降级为进程内缓存。

降级策略保证本地开发 / 单元测试不需要启动 Redis；Redis 连接异常时也不会让主流程崩溃。
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Protocol

from app.core.config import settings


class CacheBackend(Protocol):
    def get(self, key: str) -> Any | None: ...
    def setex(self, key: str, ttl: int, value: Any) -> None: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...


class InMemoryCache:
    """线程安全的进程内缓存，带过期时间。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if exp <= now]
        for k in expired:
            self._store.pop(k, None)

    def get(self, key: str) -> Any | None:
        with self._lock:
            self._purge_expired()
            item = self._store.get(key)
            return item[1] if item else None

    def setex(self, key: str, ttl: int, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for k in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(k, None)


class RedisCache:
    """Redis 实现；所有异常静默降级，避免缓存故障影响主链路。"""

    def __init__(self, url: str) -> None:
        import redis  # 延迟导入，未安装时不影响本地

        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return None

    def setex(self, key: str, ttl: int, value: Any) -> None:
        try:
            self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            pass

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except Exception:
            pass

    def delete_prefix(self, prefix: str) -> None:
        try:
            keys = self._client.scan_iter(match=f"{prefix}*")
            if keys:
                self._client.delete(*list(keys))
        except Exception:
            pass


_cache: CacheBackend | None = None


def get_cache() -> CacheBackend:
    global _cache
    if _cache is not None:
        return _cache
    if settings.redis_url:
        try:
            backend = RedisCache(settings.redis_url)
            backend._client.ping()  # type: ignore[attr-defined]
            _cache = backend
            return _cache
        except Exception:
            pass
    _cache = InMemoryCache()
    return _cache
