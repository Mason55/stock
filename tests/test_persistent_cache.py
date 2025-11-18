"""Tests for persistent cache manager"""
import pytest
import time
import json
from pathlib import Path
from src.cache.persistent_cache import PersistentCacheManager


@pytest.fixture
def cache_manager(tmp_path):
    """Create a temporary cache manager for testing"""
    db_path = tmp_path / "test_cache.db"
    manager = PersistentCacheManager(str(db_path))
    yield manager
    # Cleanup
    if db_path.exists():
        db_path.unlink()


def test_cache_set_and_get(cache_manager):
    """Test basic set and get operations"""
    key = "test:key1"
    value = {"name": "test", "value": 123}

    cache_manager.set(key, value, ttl=60)
    result = cache_manager.get(key)

    assert result == value


def test_cache_expiration(cache_manager):
    """Test cache expiration"""
    key = "test:expire"
    value = {"data": "should_expire"}

    # Set with 1 second TTL
    cache_manager.set(key, value, ttl=1)

    # Should be available immediately
    assert cache_manager.get(key) == value

    # Wait for expiration
    time.sleep(1.5)

    # Should be None after expiration
    assert cache_manager.get(key) is None


def test_cache_miss(cache_manager):
    """Test cache miss returns None"""
    result = cache_manager.get("nonexistent:key")
    assert result is None


def test_cache_update(cache_manager):
    """Test updating existing cache entry"""
    key = "test:update"
    value1 = {"version": 1}
    value2 = {"version": 2}

    cache_manager.set(key, value1, ttl=60)
    assert cache_manager.get(key) == value1

    cache_manager.set(key, value2, ttl=60)
    assert cache_manager.get(key) == value2


def test_cache_delete(cache_manager):
    """Test deleting cache entries"""
    key = "test:delete"
    value = {"data": "delete_me"}

    cache_manager.set(key, value, ttl=60)
    assert cache_manager.get(key) == value

    cache_manager.delete(key)
    assert cache_manager.get(key) is None


def test_cache_invalidate_by_pattern(cache_manager):
    """Test invalidating cache by pattern"""
    cache_manager.set("fund:600036.SH", {"pe": 10}, ttl=60)
    cache_manager.set("fund:000977.SZ", {"pe": 15}, ttl=60)
    cache_manager.set("sent:600036.SH", {"score": 0.8}, ttl=60)

    # Invalidate all fundamental data
    cache_manager.invalidate(pattern="fund:%")

    assert cache_manager.get("fund:600036.SH") is None
    assert cache_manager.get("fund:000977.SZ") is None
    assert cache_manager.get("sent:600036.SH") is not None


def test_cache_invalidate_by_stock_code(cache_manager):
    """Test invalidating cache by stock code"""
    cache_manager.set(
        "fund:600036.SH",
        {"pe": 10},
        ttl=60,
        stock_code="600036.SH"
    )
    cache_manager.set(
        "sent:600036.SH",
        {"score": 0.8},
        ttl=60,
        stock_code="600036.SH"
    )
    cache_manager.set(
        "fund:000977.SZ",
        {"pe": 15},
        ttl=60,
        stock_code="000977.SZ"
    )

    # Invalidate all data for 600036.SH
    cache_manager.invalidate(stock_code="600036.SH")

    assert cache_manager.get("fund:600036.SH") is None
    assert cache_manager.get("sent:600036.SH") is None
    assert cache_manager.get("fund:000977.SZ") is not None


def test_cache_invalidate_by_data_type(cache_manager):
    """Test invalidating cache by data type"""
    cache_manager.set(
        "fund:600036.SH",
        {"pe": 10},
        ttl=60,
        data_type="fundamental"
    )
    cache_manager.set(
        "fund:000977.SZ",
        {"pe": 15},
        ttl=60,
        data_type="fundamental"
    )
    cache_manager.set(
        "sent:600036.SH",
        {"score": 0.8},
        ttl=60,
        data_type="sentiment"
    )

    # Invalidate all fundamental data
    cache_manager.invalidate(data_type="fundamental")

    assert cache_manager.get("fund:600036.SH") is None
    assert cache_manager.get("fund:000977.SZ") is None
    assert cache_manager.get("sent:600036.SH") is not None


def test_cleanup_expired(cache_manager):
    """Test cleaning up expired entries"""
    # Add some entries with short TTL
    cache_manager.set("test:exp1", {"data": 1}, ttl=1)
    cache_manager.set("test:exp2", {"data": 2}, ttl=1)
    cache_manager.set("test:valid", {"data": 3}, ttl=60)

    # Wait for expiration
    time.sleep(1.5)

    # Cleanup
    count = cache_manager.cleanup_expired()

    assert count == 2
    assert cache_manager.get("test:valid") is not None


def test_cache_stats(cache_manager):
    """Test getting cache statistics"""
    cache_manager.set("test:1", {"data": 1}, ttl=1, data_type="test")
    cache_manager.set("test:2", {"data": 2}, ttl=60, data_type="test")
    cache_manager.set("other:1", {"data": 3}, ttl=60, data_type="other")

    # Wait for one entry to expire
    time.sleep(1.5)

    stats = cache_manager.get_stats()

    assert stats['total_entries'] == 3
    assert stats['expired_entries'] == 1
    assert stats['valid_entries'] == 2
    assert 'test' in stats['by_type']
    assert 'other' in stats['by_type']
    assert stats['db_size_bytes'] > 0


def test_max_age_override(cache_manager):
    """Test max_age parameter overrides stored TTL"""
    key = "test:max_age"
    value = {"data": "test"}

    # Set with 60s TTL
    cache_manager.set(key, value, ttl=60)

    # Should be available with default max_age
    assert cache_manager.get(key) is not None

    # Should be None with max_age=0 (immediate expiration)
    assert cache_manager.get(key, max_age=0) is None


def test_complex_value_serialization(cache_manager):
    """Test caching complex nested structures"""
    key = "test:complex"
    value = {
        "list": [1, 2, 3],
        "nested": {
            "a": "hello",
            "b": [{"x": 1}, {"y": 2}]
        },
        "float": 3.14159,
        "bool": True,
        "none": None
    }

    cache_manager.set(key, value, ttl=60)
    result = cache_manager.get(key)

    assert result == value


def test_clear_all(cache_manager):
    """Test clearing all cache entries"""
    cache_manager.set("test:1", {"data": 1}, ttl=60)
    cache_manager.set("test:2", {"data": 2}, ttl=60)
    cache_manager.set("test:3", {"data": 3}, ttl=60)

    stats_before = cache_manager.get_stats()
    assert stats_before['total_entries'] == 3

    cache_manager.clear_all()

    stats_after = cache_manager.get_stats()
    assert stats_after['total_entries'] == 0


def test_concurrent_operations(cache_manager):
    """Test multiple operations don't interfere"""
    # Set multiple keys
    for i in range(10):
        cache_manager.set(f"test:{i}", {"value": i}, ttl=60)

    # Get all keys
    for i in range(10):
        result = cache_manager.get(f"test:{i}")
        assert result == {"value": i}

    # Update some keys
    for i in range(0, 10, 2):
        cache_manager.set(f"test:{i}", {"value": i * 10}, ttl=60)

    # Verify updates
    for i in range(10):
        result = cache_manager.get(f"test:{i}")
        if i % 2 == 0:
            assert result == {"value": i * 10}
        else:
            assert result == {"value": i}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
