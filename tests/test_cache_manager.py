# tests/test_cache_manager.py - Tests for intelligent cache management
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.cache.cache_manager import (
    IntelligentCacheManager,
    SmartCacheInvalidator, 
    CacheEntry,
    CacheLevel,
    initialize_cache,
    get_cache_manager,
    cached
)


class TestSmartCacheInvalidator:
    """Test smart cache invalidation logic"""
    
    def setup_method(self):
        self.invalidator = SmartCacheInvalidator()
    
    def test_dependency_tracking(self):
        """Test cache dependency tracking"""
        
        # Add dependencies
        self.invalidator.add_dependency("stock:600036.SH", ["price:600036.SH", "volume:600036.SH"])
        self.invalidator.add_dependency("analysis:600036.SH", ["stock:600036.SH"])
        
        # Test invalidation propagation
        keys_to_invalidate = self.invalidator.get_invalidation_keys("price:600036.SH")
        
        assert "price:600036.SH" in keys_to_invalidate
        assert "stock:600036.SH" in keys_to_invalidate
        assert len(keys_to_invalidate) == 2
    
    def test_tag_based_invalidation(self):
        """Test tag-based cache invalidation"""
        
        # Tag cache entries
        self.invalidator.tag_cache_entry("price:600036.SH", ["stock_data", "real_time"])
        self.invalidator.tag_cache_entry("price:000001.SZ", ["stock_data", "real_time"])
        self.invalidator.tag_cache_entry("analysis:600036.SH", ["stock_data", "analysis"])
        
        # Test tag-based invalidation
        keys_to_invalidate = self.invalidator.get_invalidation_keys("price:600036.SH")
        
        # Should include all entries with same tags
        assert "price:600036.SH" in keys_to_invalidate
        assert "price:000001.SZ" in keys_to_invalidate
        assert "analysis:600036.SH" in keys_to_invalidate
    
    def test_pattern_matching(self):
        """Test pattern-based invalidation"""
        
        # Add some keys to tag mapping for pattern matching
        self.invalidator.tag_cache_entry("price:600036.SH", ["price"])
        self.invalidator.tag_cache_entry("price:600037.SH", ["price"])
        self.invalidator.tag_cache_entry("analysis:600036.SH", ["analysis"])
        
        # Test pattern matching
        keys = self.invalidator.invalidate_by_pattern("price:*")
        
        assert "price:600036.SH" in keys
        assert "price:600037.SH" in keys
        assert "analysis:600036.SH" not in keys


class TestIntelligentCacheManager:
    """Test intelligent cache manager"""
    
    def setup_method(self):
        # Create cache manager without Redis for testing
        self.cache = IntelligentCacheManager(
            redis_client=None,
            memory_limit_mb=1,  # Small limit for testing
            default_ttl=300
        )
    
    def test_basic_cache_operations(self):
        """Test basic cache set/get operations"""
        
        # Set cache entry
        result = self.cache.set("test_key", {"data": "test_value"}, ttl=60)
        assert result is True
        
        # Get cache entry
        cached_data, cache_level = self.cache.get("test_key")
        assert cached_data == {"data": "test_value"}
        assert cache_level == "memory"
        
        # Test cache miss
        missing_data, cache_level = self.cache.get("nonexistent_key")
        assert missing_data is None
        assert cache_level == "miss"
    
    def test_cache_with_parameters(self):
        """Test cache with parameters"""
        
        params = {"symbol": "600036.SH", "days": 30}
        
        # Set with parameters
        self.cache.set("historical_data", [1, 2, 3], params=params, ttl=60)
        
        # Get with same parameters
        cached_data, _ = self.cache.get("historical_data", params=params)
        assert cached_data == [1, 2, 3]
        
        # Get with different parameters should miss
        different_params = {"symbol": "600036.SH", "days": 60}
        cached_data, cache_level = self.cache.get("historical_data", params=different_params)
        assert cached_data is None
        assert cache_level == "miss"
    
    def test_ttl_expiration(self):
        """Test TTL-based expiration"""
        
        # Set cache entry with short TTL
        self.cache.set("short_lived", "data", ttl=1)
        
        # Should be available immediately
        cached_data, _ = self.cache.get("short_lived")
        assert cached_data == "data"
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired now
        cached_data, cache_level = self.cache.get("short_lived")
        assert cached_data is None
        assert cache_level == "miss"
    
    def test_memory_eviction(self):
        """Test LRU memory eviction"""
        
        # Fill cache beyond memory limit
        large_data = "x" * 1024 * 100  # 100KB
        
        for i in range(20):  # This should exceed 1MB limit
            self.cache.set(f"large_data_{i}", large_data, ttl=300)
        
        # Check that some entries were evicted
        stats = self.cache.get_stats()
        assert stats['memory']['usage_mb'] <= 1.1  # Allow small overflow
        assert stats['performance']['evictions']['memory'] > 0
    
    def test_smart_invalidation(self):
        """Test smart cache invalidation"""
        
        # Set cache entries with dependencies
        self.cache.set("stock_info", {"name": "招商银行"}, 
                      tags=["stock_data"], dependencies=["price_data"])
        self.cache.set("price_data", {"price": 100.0}, tags=["stock_data"])
        self.cache.set("analysis", {"score": 8.5}, 
                      tags=["analysis_data"], dependencies=["stock_info"])
        
        # Invalidate price_data - should cascade to stock_info
        invalidated = self.cache.invalidate("price_data")
        assert invalidated >= 1
        
        # Check that dependent entries were invalidated
        cached_data, _ = self.cache.get("stock_info")
        assert cached_data is None
    
    def test_tag_based_invalidation(self):
        """Test tag-based invalidation"""
        
        # Set entries with same tags
        self.cache.set("price_600036", 100.0, tags=["real_time", "prices"])
        self.cache.set("price_000001", 50.0, tags=["real_time", "prices"])
        self.cache.set("analysis_600036", {"score": 8}, tags=["analysis"])
        
        # Invalidate by tag
        invalidated = self.cache.invalidate_by_tag("real_time")
        assert invalidated == 2
        
        # Check that tagged entries were invalidated
        assert self.cache.get("price_600036")[0] is None
        assert self.cache.get("price_000001")[0] is None
        
        # Non-tagged entry should remain
        assert self.cache.get("analysis_600036")[0] is not None
    
    def test_expired_cleanup(self):
        """Test expired entry cleanup"""
        
        # Add entries with different TTLs
        self.cache.set("short_ttl", "data1", ttl=1)
        self.cache.set("long_ttl", "data2", ttl=300)
        
        time.sleep(1.1)  # Wait for short TTL to expire
        
        # Clear expired entries
        cleared = self.cache.clear_expired()
        assert cleared == 1
        
        # Check that only expired entry was removed
        assert self.cache.get("short_ttl")[0] is None
        assert self.cache.get("long_ttl")[0] == "data2"
    
    def test_cache_statistics(self):
        """Test cache statistics"""
        
        # Perform various cache operations
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.get("key1")  # Hit
        self.cache.get("key1")  # Hit
        self.cache.get("nonexistent")  # Miss
        
        stats = self.cache.get_stats()
        
        # Check statistics structure
        assert 'memory' in stats
        assert 'performance' in stats
        assert 'invalidation' in stats
        
        # Check hit/miss counts
        assert stats['performance']['hits']['memory'] == 2
        assert stats['performance']['misses']['total'] == 1
        
        # Check memory usage
        assert stats['memory']['entries'] == 2
        assert stats['memory']['usage_bytes'] > 0


class TestCacheDecorator:
    """Test cache decorator functionality"""
    
    def setup_method(self):
        # Initialize global cache for decorator testing
        global cache_manager
        import src.cache.cache_manager as cache_module
        cache_module.cache_manager = IntelligentCacheManager(
            redis_client=None,
            memory_limit_mb=10
        )
    
    def test_function_caching(self):
        """Test function result caching"""
        
        call_count = 0
        
        @cached(ttl=60, tags=['test_func'])
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # First call should execute function
        result1 = expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1
        
        # Second call should use cache
        result2 = expensive_function(1, 2)
        assert result2 == 3
        assert call_count == 1  # Should not increment
        
        # Different parameters should execute function again
        result3 = expensive_function(2, 3)
        assert result3 == 5
        assert call_count == 2
    
    def test_cache_decorator_with_custom_key(self):
        """Test cache decorator with custom key function"""
        
        call_count = 0
        
        @cached(ttl=60, key_func=lambda stock_code: f"stock:{stock_code}")
        def get_stock_data(stock_code):
            nonlocal call_count
            call_count += 1
            return {"code": stock_code, "price": 100.0}
        
        # Test caching with custom key
        result1 = get_stock_data("600036.SH")
        result2 = get_stock_data("600036.SH")
        
        assert result1 == result2
        assert call_count == 1
    
    def test_cache_decorator_without_manager(self):
        """Test cache decorator behavior when manager is not available"""
        
        # Temporarily disable cache manager
        import src.cache.cache_manager as cache_module
        original_manager = cache_module.cache_manager
        cache_module.cache_manager = None
        
        try:
            call_count = 0
            
            @cached(ttl=60)
            def uncached_function(x):
                nonlocal call_count
                call_count += 1
                return x * 2
            
            # Should execute function every time without cache
            result1 = uncached_function(5)
            result2 = uncached_function(5)
            
            assert result1 == result2 == 10
            assert call_count == 2  # Called twice without caching
            
        finally:
            # Restore cache manager
            cache_module.cache_manager = original_manager


class TestCacheIntegration:
    """Test cache integration scenarios"""
    
    def setup_method(self):
        # Mock Redis client for testing
        self.mock_redis = MagicMock()
        self.cache = IntelligentCacheManager(
            redis_client=self.mock_redis,
            memory_limit_mb=1
        )
    
    def test_redis_fallback(self):
        """Test fallback when Redis is unavailable"""
        
        # Configure Redis to fail
        self.mock_redis.setex.side_effect = Exception("Redis connection failed")
        self.mock_redis.get.side_effect = Exception("Redis connection failed")
        
        # Operations should still work with memory cache
        self.cache.set("test_key", "test_value")
        cached_data, cache_level = self.cache.get("test_key")
        
        assert cached_data == "test_value"
        assert cache_level == "memory"
    
    def test_memory_to_redis_promotion(self):
        """Test promotion of hot data to Redis"""
        
        # Set data in memory
        self.cache.set("hot_data", "valuable_data", ttl=300)
        
        # Simulate memory pressure by adding large data
        large_data = "x" * 1024 * 500  # 500KB
        for i in range(5):
            self.cache.set(f"large_{i}", large_data)
        
        # The hot data might be promoted to Redis during eviction
        # (This tests the eviction logic that tries to save valuable data)
        stats = self.cache.get_stats()
        assert stats['memory']['usage_mb'] <= 1.1
    
    def test_comprehensive_cache_workflow(self):
        """Test comprehensive caching workflow"""
        
        # 1. Set initial data with tags and dependencies
        self.cache.set("base_data", {"value": 1}, 
                      tags=["group1"], dependencies=[])
        self.cache.set("derived_data", {"value": 2}, 
                      tags=["group1"], dependencies=["base_data"])
        
        # 2. Access data to build usage statistics
        for _ in range(5):
            self.cache.get("base_data")
        
        # 3. Invalidate and check cascading
        self.cache.invalidate("base_data")
        
        # Both entries should be invalidated due to dependency and tags
        assert self.cache.get("base_data")[0] is None
        assert self.cache.get("derived_data")[0] is None
        
        # 4. Check statistics
        stats = self.cache.get_stats()
        assert stats['performance']['hits']['memory'] >= 5
        assert stats['performance']['invalidations']['total'] >= 1


class TestCacheManagerInitialization:
    """Test cache manager initialization and global state"""
    
    def test_cache_initialization(self):
        """Test cache manager initialization"""
        
        # Test initialization without Redis
        manager = initialize_cache(redis_client=None, memory_limit_mb=64)
        assert manager is not None
        assert manager.memory_limit_bytes == 64 * 1024 * 1024
        
        # Test global manager access
        global_manager = get_cache_manager()
        assert global_manager is manager
    
    def test_cache_initialization_with_redis(self):
        """Test cache initialization with Redis"""
        
        mock_redis = MagicMock()
        manager = initialize_cache(redis_client=mock_redis, memory_limit_mb=128)
        
        assert manager is not None
        assert manager.redis_client is mock_redis
        assert manager.memory_limit_bytes == 128 * 1024 * 1024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])