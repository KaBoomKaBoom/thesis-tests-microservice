"""
cache.py
--------
Redis client singleton.
Provides a single shared connection pool for the entire application.
"""

import redis
from app.config import get_settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """
    Return the shared Redis client, creating it on first call.
    Connection errors are raised to the caller so FastAPI can return
    a proper 503 instead of crashing the process.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,   # keys and values are plain str
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client
