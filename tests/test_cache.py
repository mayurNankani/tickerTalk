"""Unit tests for TTLCache utility."""
import sys, os, time, threading
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web')))

import pytest
from utils.cache import TTLCache


class TestTTLCache:
    def test_basic_set_get(self):
        cache = TTLCache(default_ttl=60)
        cache.set("k", "v")
        assert cache.get("k") == "v"

    def test_missing_key_returns_none(self):
        cache = TTLCache()
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = TTLCache()
        cache.set("k", "v", ttl=0)  # expires immediately
        # Force time to advance past TTL by checking after a tiny sleep
        time.sleep(0.01)
        assert cache.get("k") is None

    def test_delete(self):
        cache = TTLCache()
        cache.set("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_clear(self):
        cache = TTLCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0

    def test_len(self):
        cache = TTLCache()
        assert len(cache) == 0
        cache.set("x", 1)
        assert len(cache) == 1

    def test_thread_safety(self):
        """Concurrent writes should not corrupt internal state."""
        cache = TTLCache()
        errors = []

        def writer(i):
            try:
                for j in range(50):
                    cache.set(f"key_{i}_{j}", i * j)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread safety errors: {errors}"
