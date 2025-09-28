# src/cache/cache_manager.py - Intelligent cache management with smart invalidation
import json
import hashlib
import time
import logging
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from threading import Lock
from collections import defaultdict, OrderedDict
import redis
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache level priority"""
    MEMORY = 1
    REDIS = 2
    DISK = 3


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    data: Any
    created_at: datetime
    expires_at: datetime
    access_count: int
    last_access: datetime
    cache_level: CacheLevel
    tags: List[str]
    size_bytes: int
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
    
    def is_hot(self) -> bool:
        """Check if data is frequently accessed (hot data)"""
        recent_threshold = datetime.now() - timedelta(hours=1)
        return self.access_count > 10 and self.last_access > recent_threshold


class SmartCacheInvalidator:
    """Smart cache invalidation strategies"""
    
    def __init__(self):
        self.dependency_graph = defaultdict(set)  # key -> dependent keys
        self.tag_mapping = defaultdict(set)  # tag -> keys
        self._lock = Lock()
    
    def add_dependency(self, key: str, depends_on: List[str]):
        """Add cache dependencies"""
        with self._lock:
            for dep in depends_on:
                self.dependency_graph[dep].add(key)
    
    def tag_cache_entry(self, key: str, tags: List[str]):
        """Tag cache entry for group invalidation"""
        with self._lock:
            for tag in tags:
                self.tag_mapping[tag].add(key)
    
    def get_invalidation_keys(self, changed_key: str) -> set:
        """Get all keys that should be invalidated when changed_key is modified"""
        with self._lock:
            keys_to_invalidate = {changed_key}
            
            # Add dependent keys
            keys_to_invalidate.update(self.dependency_graph.get(changed_key, set()))
            
            # Add keys with same tags
            for tag in self.tag_mapping:
                if changed_key in self.tag_mapping[tag]:
                    keys_to_invalidate.update(self.tag_mapping[tag])
            
            return keys_to_invalidate
    
    def invalidate_by_pattern(self, pattern: str) -> set:
        """Get keys matching a pattern for invalidation"""
        import re
        regex = re.compile(pattern.replace('*', '.*'))
        
        matching_keys = set()
        with self._lock:
            # Check dependency graph keys
            for key in self.dependency_graph:
                if regex.match(key):
                    matching_keys.add(key)
            
            # Check tag mapping keys
            for tag_keys in self.tag_mapping.values():
                for key in tag_keys:
                    if regex.match(key):
                        matching_keys.add(key)
        
        return matching_keys


class IntelligentCacheManager:
    """Multi-level intelligent cache manager with smart invalidation"""
    
    def __init__(self, 
                 redis_client: Optional[redis.Redis] = None,
                 memory_limit_mb: int = 256,
                 default_ttl: int = 3600):
        
        self.redis_client = redis_client
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.default_ttl = default_ttl
        
        # Memory cache with LRU
        self.memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.memory_usage = 0
        
        # Cache statistics
        self.stats = {
            'hits': defaultdict(int),
            'misses': defaultdict(int),
            'evictions': defaultdict(int),
            'invalidations': defaultdict(int)
        }
        
        # Smart invalidation
        self.invalidator = SmartCacheInvalidator()
        
        # Thread safety
        self._lock = Lock()
        
        logger.info(f"Initialized cache manager with {memory_limit_mb}MB memory limit")
    
    def _generate_key(self, key: str, params: Dict = None) -> str:
        """Generate cache key with parameters"""
        if params:
            param_str = json.dumps(params, sort_keys=True)
            key_hash = hashlib.md5(f"{key}:{param_str}".encode()).hexdigest()[:8]
            return f"{key}:{key_hash}"
        return key
    
    def _calculate_size(self, data: Any) -> int:
        """Calculate approximate size of data in bytes"""
        try:
            if isinstance(data, (str, bytes)):
                return len(data)
            elif isinstance(data, dict):
                return len(json.dumps(data))
            elif hasattr(data, '__sizeof__'):
                return data.__sizeof__()
            else:
                return len(str(data))
        except Exception:
            return 1024  # Default size
    
    def _evict_from_memory(self, needed_bytes: int):
        """Evict entries from memory cache using LRU + intelligence"""
        with self._lock:
            while self.memory_usage + needed_bytes > self.memory_limit_bytes and self.memory_cache:
                # Find best candidate for eviction
                evict_key = None
                min_score = float('inf')
                
                for key, entry in self.memory_cache.items():
                    # Calculate eviction score (lower = better candidate)
                    score = entry.access_count
                    
                    # Penalize recent access
                    time_since_access = (datetime.now() - entry.last_access).total_seconds()
                    if time_since_access < 300:  # 5 minutes
                        score += 100
                    
                    # Penalize hot data
                    if entry.is_hot():
                        score += 50
                    
                    # Prefer expired data
                    if entry.is_expired():
                        score -= 50
                    
                    if score < min_score:
                        min_score = score
                        evict_key = key
                
                if evict_key:
                    entry = self.memory_cache.pop(evict_key)
                    self.memory_usage -= entry.size_bytes
                    self.stats['evictions']['memory'] += 1
                    
                    # Try to promote to Redis if available and valuable
                    if self.redis_client and entry.is_hot():
                        self._store_in_redis(evict_key, entry)
    
    def _store_in_memory(self, key: str, data: Any, ttl: int, tags: List[str] = None) -> CacheEntry:
        """Store data in memory cache"""
        size_bytes = self._calculate_size(data)
        
        # Evict if necessary
        self._evict_from_memory(size_bytes)
        
        entry = CacheEntry(
            key=key,
            data=data,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=ttl),
            access_count=0,
            last_access=datetime.now(),
            cache_level=CacheLevel.MEMORY,
            tags=tags or [],
            size_bytes=size_bytes
        )
        
        with self._lock:
            self.memory_cache[key] = entry
            self.memory_cache.move_to_end(key)  # Mark as recently used
            self.memory_usage += size_bytes
            
            # Register for smart invalidation
            if tags:
                self.invalidator.tag_cache_entry(key, tags)
        
        return entry
    
    def _store_in_redis(self, key: str, entry_or_data, ttl: int = None):
        """Store data in Redis"""
        if not self.redis_client:
            return
        
        try:
            if isinstance(entry_or_data, CacheEntry):
                data = entry_or_data.data
                ttl = ttl or int((entry_or_data.expires_at - datetime.now()).total_seconds())
            else:
                data = entry_or_data
                ttl = ttl or self.default_ttl
            
            serialized = json.dumps({
                'data': data,
                'created_at': datetime.now().isoformat(),
                'cache_level': 'redis'
            })
            
            self.redis_client.setex(f"cache:{key}", ttl, serialized)
            
        except Exception as e:
            logger.warning(f"Failed to store in Redis: {e}")
    
    def _get_from_memory(self, key: str) -> Optional[CacheEntry]:
        """Get data from memory cache"""
        with self._lock:
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                
                if entry.is_expired():
                    self.memory_cache.pop(key)
                    self.memory_usage -= entry.size_bytes
                    return None
                
                # Update access statistics
                entry.access_count += 1
                entry.last_access = datetime.now()
                
                # Move to end (mark as recently used)
                self.memory_cache.move_to_end(key)
                
                return entry
        
        return None
    
    def _get_from_redis(self, key: str) -> Optional[Any]:
        """Get data from Redis"""
        if not self.redis_client:
            return None
        
        try:
            cached = self.redis_client.get(f"cache:{key}")
            if cached:
                data = json.loads(cached)
                return data['data']
        except Exception as e:
            logger.warning(f"Failed to get from Redis: {e}")
        
        return None
    
    def set(self, key: str, data: Any, ttl: int = None, 
            params: Dict = None, tags: List[str] = None, 
            dependencies: List[str] = None) -> bool:
        """Set cache entry with smart invalidation support"""
        
        cache_key = self._generate_key(key, params)
        ttl = ttl or self.default_ttl
        
        # Store in memory first (L1 cache)
        self._store_in_memory(cache_key, data, ttl, tags)
        
        # Store in Redis (L2 cache)
        self._store_in_redis(cache_key, data, ttl)
        
        # Register dependencies
        if dependencies:
            self.invalidator.add_dependency(cache_key, dependencies)
        
        logger.debug(f"Cached data with key: {cache_key}, TTL: {ttl}, Tags: {tags}")
        return True
    
    def get(self, key: str, params: Dict = None) -> Tuple[Optional[Any], str]:
        """Get cached data with cache level info"""
        
        cache_key = self._generate_key(key, params)
        
        # Try memory cache first (L1)
        entry = self._get_from_memory(cache_key)
        if entry:
            self.stats['hits']['memory'] += 1
            return entry.data, 'memory'
        
        # Try Redis cache (L2)
        redis_data = self._get_from_redis(cache_key)
        if redis_data:
            self.stats['hits']['redis'] += 1
            
            # Promote to memory if valuable
            self._store_in_memory(cache_key, redis_data, self.default_ttl)
            
            return redis_data, 'redis'
        
        # Cache miss
        self.stats['misses']['total'] += 1
        return None, 'miss'
    
    def invalidate(self, key: str, params: Dict = None, pattern: bool = False) -> int:
        """Intelligent cache invalidation"""
        
        if pattern:
            keys_to_invalidate = self.invalidator.invalidate_by_pattern(key)
        else:
            cache_key = self._generate_key(key, params)
            keys_to_invalidate = self.invalidator.get_invalidation_keys(cache_key)
        
        invalidated_count = 0
        
        with self._lock:
            for inv_key in keys_to_invalidate:
                # Remove from memory
                if inv_key in self.memory_cache:
                    entry = self.memory_cache.pop(inv_key)
                    self.memory_usage -= entry.size_bytes
                    invalidated_count += 1
                
                # Remove from Redis
                if self.redis_client:
                    try:
                        self.redis_client.delete(f"cache:{inv_key}")
                    except Exception as e:
                        logger.warning(f"Failed to delete from Redis: {e}")
        
        self.stats['invalidations']['total'] += invalidated_count
        
        if invalidated_count > 0:
            logger.info(f"Invalidated {invalidated_count} cache entries")
        
        return invalidated_count
    
    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with a specific tag"""
        with self._lock:
            keys_to_invalidate = self.invalidator.tag_mapping.get(tag, set()).copy()
        
        invalidated_count = 0
        for key in keys_to_invalidate:
            self.invalidate(key)
            invalidated_count += 1
        
        return invalidated_count
    
    def clear_expired(self) -> int:
        """Clear expired entries from memory cache"""
        expired_count = 0
        
        with self._lock:
            expired_keys = [
                key for key, entry in self.memory_cache.items() 
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                entry = self.memory_cache.pop(key)
                self.memory_usage -= entry.size_bytes
                expired_count += 1
        
        if expired_count > 0:
            logger.info(f"Cleared {expired_count} expired cache entries")
        
        return expired_count
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self._lock:
            memory_entries = len(self.memory_cache)
            hot_entries = sum(1 for entry in self.memory_cache.values() if entry.is_hot())
            
            return {
                'memory': {
                    'entries': memory_entries,
                    'usage_bytes': self.memory_usage,
                    'usage_mb': round(self.memory_usage / (1024 * 1024), 2),
                    'limit_mb': round(self.memory_limit_bytes / (1024 * 1024), 2),
                    'usage_percent': round(self.memory_usage / self.memory_limit_bytes * 100, 1),
                    'hot_entries': hot_entries
                },
                'redis': {
                    'enabled': self.redis_client is not None
                },
                'performance': dict(self.stats),
                'invalidation': {
                    'dependencies': len(self.invalidator.dependency_graph),
                    'tag_groups': len(self.invalidator.tag_mapping)
                }
            }


# Global cache manager instance
cache_manager: Optional[IntelligentCacheManager] = None


def initialize_cache(redis_client: Optional[redis.Redis] = None, 
                    memory_limit_mb: int = 256) -> IntelligentCacheManager:
    """Initialize global cache manager"""
    global cache_manager
    
    cache_manager = IntelligentCacheManager(
        redis_client=redis_client,
        memory_limit_mb=memory_limit_mb
    )
    
    logger.info("Cache manager initialized successfully")
    return cache_manager


def get_cache_manager() -> Optional[IntelligentCacheManager]:
    """Get global cache manager instance"""
    return cache_manager


# Cache decorators
def cached(ttl: int = 3600, tags: List[str] = None, 
          dependencies: List[str] = None, key_func=None):
    """Decorator for caching function results"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not cache_manager:
                return func(*args, **kwargs)
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                params = {'args': args, 'kwargs': kwargs}
                cache_key = f"{func.__module__}.{func.__name__}"
            
            # Try to get from cache
            if not key_func:
                cached_result, cache_level = cache_manager.get(cache_key, params=params)
            else:
                cached_result, cache_level = cache_manager.get(cache_key)
            
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__} from {cache_level}")
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if not key_func:
                cache_manager.set(
                    cache_key, result, ttl=ttl, params=params,
                    tags=tags, dependencies=dependencies
                )
            else:
                cache_manager.set(
                    cache_key, result, ttl=ttl, 
                    tags=tags, dependencies=dependencies
                )
            
            logger.debug(f"Cached result for {func.__name__}")
            return result
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator