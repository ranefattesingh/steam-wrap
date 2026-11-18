import time

from steam_wrap.cache import MemoryTTLCache


def test_ttl_expiry(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cache = MemoryTTLCache()
    now = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: now)
    cache.set("k", 1, ttl_seconds=10)
    assert cache.get("k") == 1
    monkeypatch.setattr(time, "monotonic", lambda: now + 11)
    assert cache.get("k") is None


def test_lru_eviction() -> None:
    cache = MemoryTTLCache(max_entries=2)
    cache.set("a", 1, 60)
    cache.set("b", 2, 60)
    cache.get("a")  # a becomes most recent
    cache.set("c", 3, 60)
    assert cache.get("b") is None
    assert cache.get("a") == 1 and cache.get("c") == 3


def test_zero_ttl_is_not_stored() -> None:
    cache = MemoryTTLCache()
    cache.set("a", 1, 0)
    assert cache.get("a") is None
