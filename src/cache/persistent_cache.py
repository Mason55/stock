"""Persistent cache manager using SQLite backend

Provides TTL-based caching for crawled data to reduce API rate limits
and improve performance.
"""
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PersistentCacheManager:
    """SQLite-based persistent cache for crawled data"""

    def __init__(self, db_path: str = "cache.db"):
        """Initialize persistent cache with SQLite backend

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"Persistent cache initialized: {self.db_path}")

    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_store (
                    cache_key TEXT PRIMARY KEY,
                    cache_value TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    data_type TEXT,
                    stock_code TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires
                ON cache_store(expires_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_stock_code
                ON cache_store(stock_code)
            """)

            conn.commit()
            logger.debug("Database schema initialized")

    def get(self, key: str, max_age: int = 3600) -> Optional[Any]:
        """Get cached value if not expired

        Args:
            key: Cache key
            max_age: Maximum age in seconds (overrides stored TTL)

        Returns:
            Cached value or None if not found/expired
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT cache_value, created_at, expires_at
                    FROM cache_store
                    WHERE cache_key = ?
                    """,
                    (key,)
                )
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"Cache miss: {key}")
                    return None

                current_time = int(time.time())

                # Check expiration
                if row['expires_at'] <= current_time:
                    logger.debug(f"Cache expired: {key}")
                    self.delete(key)
                    return None

                # Check max_age override
                age = current_time - row['created_at']
                if age >= max_age:
                    logger.debug(f"Cache too old: {key} (age={age}s, max={max_age}s)")
                    return None

                # Deserialize value
                value = json.loads(row['cache_value'])
                logger.debug(f"Cache hit: {key} (age={age}s)")
                return value

        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600,
            data_type: str = None, stock_code: str = None):
        """Set cache value with TTL

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds
            data_type: Type of data (e.g., 'fundamental', 'sentiment')
            stock_code: Associated stock code
        """
        try:
            current_time = int(time.time())
            expires_at = current_time + ttl

            # Serialize value
            serialized_value = json.dumps(value, ensure_ascii=False)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_store
                    (cache_key, cache_value, created_at, expires_at, data_type, stock_code)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (key, serialized_value, current_time, expires_at, data_type, stock_code)
                )
                conn.commit()

            logger.debug(f"Cache set: {key} (ttl={ttl}s, expires={datetime.fromtimestamp(expires_at)})")

        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

    def delete(self, key: str):
        """Delete cache entry

        Args:
            key: Cache key
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_store WHERE cache_key = ?", (key,))
                conn.commit()
                logger.debug(f"Cache deleted: {key}")
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")

    def invalidate(self, pattern: str = None, stock_code: str = None,
                   data_type: str = None):
        """Invalidate cache by pattern, stock_code, or data_type

        Args:
            pattern: SQL LIKE pattern for cache_key (e.g., 'fundamental:%')
            stock_code: Stock code to invalidate
            data_type: Data type to invalidate
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if pattern:
                    conn.execute(
                        "DELETE FROM cache_store WHERE cache_key LIKE ?",
                        (pattern,)
                    )
                    logger.info(f"Invalidated cache matching pattern: {pattern}")

                if stock_code:
                    conn.execute(
                        "DELETE FROM cache_store WHERE stock_code = ?",
                        (stock_code,)
                    )
                    logger.info(f"Invalidated cache for stock: {stock_code}")

                if data_type:
                    conn.execute(
                        "DELETE FROM cache_store WHERE data_type = ?",
                        (data_type,)
                    )
                    logger.info(f"Invalidated cache for data_type: {data_type}")

                conn.commit()

        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")

    def cleanup_expired(self) -> int:
        """Remove expired cache entries

        Returns:
            Number of entries removed
        """
        try:
            current_time = int(time.time())
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM cache_store WHERE expires_at <= ?",
                    (current_time,)
                )
                count = cursor.rowcount
                conn.commit()

            if count > 0:
                logger.info(f"Cleaned up {count} expired cache entries")
            return count

        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics

        Returns:
            Dictionary with cache statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row

                # Total entries
                cursor = conn.execute("SELECT COUNT(*) as total FROM cache_store")
                total = cursor.fetchone()['total']

                # Expired entries
                current_time = int(time.time())
                cursor = conn.execute(
                    "SELECT COUNT(*) as expired FROM cache_store WHERE expires_at <= ?",
                    (current_time,)
                )
                expired = cursor.fetchone()['expired']

                # By data type
                cursor = conn.execute("""
                    SELECT data_type, COUNT(*) as count
                    FROM cache_store
                    GROUP BY data_type
                """)
                by_type = {row['data_type']: row['count'] for row in cursor.fetchall()}

                # Database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    'total_entries': total,
                    'expired_entries': expired,
                    'valid_entries': total - expired,
                    'by_type': by_type,
                    'db_size_bytes': db_size,
                    'db_size_mb': round(db_size / 1024 / 1024, 2)
                }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {
                'total_entries': 0,
                'expired_entries': 0,
                'valid_entries': 0,
                'by_type': {},
                'db_size_bytes': 0,
                'db_size_mb': 0
            }

    def clear_all(self):
        """Clear all cache entries (use with caution)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache_store")
                conn.commit()
            logger.warning("All cache entries cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")


# Global instance
_cache_manager: Optional[PersistentCacheManager] = None


def get_persistent_cache(db_path: str = "cache.db") -> PersistentCacheManager:
    """Get or create global persistent cache manager

    Args:
        db_path: Path to SQLite database file

    Returns:
        Global PersistentCacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = PersistentCacheManager(db_path)
    return _cache_manager
