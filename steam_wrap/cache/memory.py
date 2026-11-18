"""In-memory TTL + LRU cache.

The service layer depends only on the :class:`CacheBackend` protocol, so a
shared backend (e.g. Redis) can be dropped in later for multi-process
deployments without touching business logic.

Note: with several uvicorn workers each process keeps its own cache.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Protocol


class CacheBackend(Protocol):
    """Minimal cache interface used by the services."""

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl_seconds: float) -> None: ...

    def delete(self, key: str) -> None: ...

    def clear(self) -> None: ...


class MemoryTTLCache:
    """Bounded dict with per-entry expiry and least-recently-used eviction.

    All operations are synchronous and do not await, so they are safe to call
    from any coroutine on a single event loop without locking.
    """

    def __init__(self, max_entries: int = 10_000) -> None:
        self._max_entries = max_entries
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at <= time.monotonic():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            return
        self._data[key] = (time.monotonic() + ttl_seconds, value)
        self._data.move_to_end(key)
        while len(self._data) > self._max_entries:
            self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
