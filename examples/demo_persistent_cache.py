#!/usr/bin/env python
"""Demo script to show persistent cache functionality"""
import sys
import time
from src.cache.persistent_cache import get_persistent_cache

def demo_basic_usage():
    """Demonstrate basic cache operations"""
    print("=" * 60)
    print("DEMO 1: Basic Cache Operations")
    print("=" * 60)

    cache = get_persistent_cache("demo_cache.db")

    # Set some values
    print("\n1. Setting cache values...")
    cache.set("stock:600036.SH", {"name": "招商银行", "price": 45.5}, ttl=60)
    cache.set("stock:000977.SZ", {"name": "浪潮信息", "price": 75.96}, ttl=60)
    cache.set("stock:159920.SZ", {"name": "恒生ETF", "price": 1.61}, ttl=60)
    print("   ✓ Cached 3 stocks")

    # Get values
    print("\n2. Getting cached values...")
    stock1 = cache.get("stock:600036.SH")
    print(f"   {stock1['name']}: ¥{stock1['price']}")

    stock2 = cache.get("stock:000977.SZ")
    print(f"   {stock2['name']}: ¥{stock2['price']}")

    # Cache miss
    print("\n3. Testing cache miss...")
    result = cache.get("stock:nonexistent")
    print(f"   Non-existent key: {result}")

    # Stats
    print("\n4. Cache statistics:")
    stats = cache.get_stats()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   Valid entries: {stats['valid_entries']}")
    print(f"   Database size: {stats['db_size_mb']} MB")


def demo_expiration():
    """Demonstrate cache expiration"""
    print("\n" + "=" * 60)
    print("DEMO 2: Cache Expiration")
    print("=" * 60)

    cache = get_persistent_cache("demo_cache.db")

    # Set with short TTL
    print("\n1. Setting value with 2-second TTL...")
    cache.set("temp:test", {"data": "expires soon"}, ttl=2)
    print("   ✓ Value cached")

    # Immediate retrieval
    print("\n2. Retrieving immediately...")
    value = cache.get("temp:test")
    print(f"   Retrieved: {value}")

    # Wait and retry
    print("\n3. Waiting 2.5 seconds...")
    time.sleep(2.5)
    value = cache.get("temp:test")
    print(f"   After expiration: {value}")


def demo_invalidation():
    """Demonstrate cache invalidation"""
    print("\n" + "=" * 60)
    print("DEMO 3: Cache Invalidation")
    print("=" * 60)

    cache = get_persistent_cache("demo_cache.db")

    # Set multiple values
    print("\n1. Setting multiple values...")
    cache.set("fund:600036.SH", {"pe": 5.5}, ttl=3600, data_type="fundamental", stock_code="600036.SH")
    cache.set("fund:000977.SZ", {"pe": 45.2}, ttl=3600, data_type="fundamental", stock_code="000977.SZ")
    cache.set("sent:600036.SH", {"score": 0.8}, ttl=3600, data_type="sentiment", stock_code="600036.SH")
    print("   ✓ Cached 3 values")

    # Invalidate by pattern
    print("\n2. Invalidating all fundamental data (fund:*)...")
    cache.invalidate(pattern="fund:%")
    print("   ✓ Invalidated")

    # Check results
    print("\n3. Checking results...")
    fund1 = cache.get("fund:600036.SH")
    fund2 = cache.get("fund:000977.SZ")
    sent1 = cache.get("sent:600036.SH")
    print(f"   fund:600036.SH: {fund1}")
    print(f"   fund:000977.SZ: {fund2}")
    print(f"   sent:600036.SH: {sent1}")

    # Invalidate by stock code
    print("\n4. Invalidating all data for 600036.SH...")
    cache.set("fund:600036.SH", {"pe": 5.5}, ttl=3600, stock_code="600036.SH")
    cache.invalidate(stock_code="600036.SH")
    print("   ✓ Invalidated")

    sent1 = cache.get("sent:600036.SH")
    print(f"   sent:600036.SH after invalidation: {sent1}")


def demo_real_world():
    """Demonstrate real-world usage with stock analysis"""
    print("\n" + "=" * 60)
    print("DEMO 4: Real-World Usage - Stock Analysis Cache")
    print("=" * 60)

    from src.services.fundamental_provider import FundamentalDataProvider
    from src.services.sentiment_provider import SentimentDataProvider

    fundamental_provider = FundamentalDataProvider(use_persistent_cache=True)
    sentiment_provider = SentimentDataProvider(use_persistent_cache=True)

    stock_code = "159920.SZ"

    # First request (will crawl/fetch)
    print(f"\n1. First request for {stock_code} (cold cache)...")
    start = time.time()
    fundamental = fundamental_provider.get_fundamental_analysis(stock_code)
    sentiment = sentiment_provider.get_sentiment_analysis(stock_code)
    first_time = time.time() - start
    print(f"   ✓ Completed in {first_time:.2f}s")
    if fundamental:
        print(f"   Fundamental source: {fundamental.get('source', 'N/A')}")
    if sentiment:
        print(f"   Sentiment source: {sentiment.get('source', 'N/A')}")

    # Second request (from cache)
    print(f"\n2. Second request for {stock_code} (hot cache)...")
    start = time.time()
    fundamental = fundamental_provider.get_fundamental_analysis(stock_code)
    sentiment = sentiment_provider.get_sentiment_analysis(stock_code)
    second_time = time.time() - start
    print(f"   ✓ Completed in {second_time:.2f}s")
    print(f"   Speedup: {first_time/second_time:.1f}x faster")

    # Cache stats
    cache = get_persistent_cache()
    stats = cache.get_stats()
    print(f"\n3. Final cache statistics:")
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   By type: {stats['by_type']}")
    print(f"   Database size: {stats['db_size_mb']} MB")


def cleanup():
    """Cleanup demo cache"""
    print("\n" + "=" * 60)
    print("Cleanup")
    print("=" * 60)
    cache = get_persistent_cache("demo_cache.db")
    cache.clear_all()
    print("✓ All demo cache cleared")


if __name__ == "__main__":
    try:
        demo_basic_usage()
        demo_expiration()
        demo_invalidation()
        demo_real_world()
    finally:
        cleanup()
        print("\n" + "=" * 60)
        print("Demo completed!")
        print("=" * 60)
