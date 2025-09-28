# src/middleware/rate_limiter.py
import time
import redis
from functools import wraps
from flask import request, jsonify
from config.settings import settings


class RateLimiter:
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, dict]:
        """
        Token bucket algorithm
        Args:
            key: unique identifier (e.g., IP address or user ID)
            limit: max requests per window
            window: time window in seconds
        """
        current_time = int(time.time())
        bucket_key = f"rate_limit:{key}:{current_time // window}"
        
        pipe = self.redis.pipeline()
        pipe.incr(bucket_key)
        pipe.expire(bucket_key, window * 2)
        results = pipe.execute()
        
        request_count = results[0]
        
        remaining = max(0, limit - request_count)
        reset_time = (current_time // window + 1) * window
        
        return request_count <= limit, {
            'limit': limit,
            'remaining': remaining,
            'reset': reset_time
        }
    
    def limit(self, max_requests: int = 100, window: int = 60, key_func=None):
        """
        Decorator for rate limiting endpoints
        """
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                if key_func:
                    key = key_func()
                else:
                    key = request.remote_addr or 'unknown'
                
                allowed, info = self.is_allowed(key, max_requests, window)
                
                if not allowed:
                    response = jsonify({
                        'error': 'Rate limit exceeded',
                        'retry_after': info['reset'] - int(time.time())
                    })
                    response.status_code = 429
                    response.headers['X-RateLimit-Limit'] = str(info['limit'])
                    response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                    response.headers['X-RateLimit-Reset'] = str(info['reset'])
                    response.headers['Retry-After'] = str(info['reset'] - int(time.time()))
                    return response
                
                response = f(*args, **kwargs)
                
                if hasattr(response, 'headers'):
                    response.headers['X-RateLimit-Limit'] = str(info['limit'])
                    response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                    response.headers['X-RateLimit-Reset'] = str(info['reset'])
                
                return response
            return wrapped
        return decorator


def get_redis_client():
    """Initialize Redis client"""
    try:
        client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        client.ping()
        return client
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Redis: {e}")