# src/middleware/cache.py
import json
import hashlib
from functools import wraps
from typing import Optional, Any
import redis
from flask import request
from config.settings import settings


class CacheManager:
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.local_cache = {}
        self.local_cache_max_size = 1000
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get from L1 (local) then L2 (Redis)"""
        if key in self.local_cache:
            return self.local_cache[key]
        
        try:
            value = self.redis.get(key)
            if value:
                decoded = json.loads(value)
                self._set_local(key, decoded)
                return decoded
        except Exception:
            pass
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Set to both L1 and L2 cache"""
        self._set_local(key, value)
        
        try:
            self.redis.setex(key, ttl, json.dumps(value))
        except Exception:
            pass
    
    def _set_local(self, key: str, value: Any):
        """Set local cache with size limit"""
        if len(self.local_cache) >= self.local_cache_max_size:
            first_key = next(iter(self.local_cache))
            del self.local_cache[first_key]
        
        self.local_cache[key] = value
    
    def delete(self, key: str):
        """Delete from both caches"""
        if key in self.local_cache:
            del self.local_cache[key]
        
        try:
            self.redis.delete(key)
        except Exception:
            pass
    
    def cached(self, ttl: int = 300, key_prefix: str = None):
        """
        Decorator for caching function results
        """
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                prefix = key_prefix or f.__name__
                cache_key = self._generate_cache_key(prefix, *args, **kwargs)
                
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                result = f(*args, **kwargs)
                
                if result is not None:
                    self.set(cache_key, result, ttl)
                
                return result
            return wrapped
        return decorator
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate all cache keys matching pattern"""
        self.local_cache.clear()
        
        try:
            for key in self.redis.scan_iter(match=f"cache:*{pattern}*"):
                self.redis.delete(key)
        except Exception:
            pass