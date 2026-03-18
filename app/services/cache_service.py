"""
cache_service.py
----------------
Helpers for caching GenerateTestResponse objects in Redis.

Key scheme:  test:{test_id}
TTL:         86400 seconds (24 hours)
Serialisation: JSON via Pydantic's model_dump_json / model_validate_json
"""

import logging
from typing import Optional

import redis

from app.models.test import GenerateTestResponse

logger = logging.getLogger(__name__)

TEST_TTL_SECONDS = 86_400   # 24 hours
_KEY_PREFIX = "test:"


def _key(test_id: int) -> str:
    return f"{_KEY_PREFIX}{test_id}"


def cache_get_test(r: redis.Redis, test_id: int) -> Optional[GenerateTestResponse]:
    """
    Fetch a cached GenerateTestResponse from Redis.
    Returns None on cache miss or any Redis/deserialization error.
    """
    key = _key(test_id)
    logger.debug("Redis GET  key=%s", key)
    try:
        raw = r.get(key)
        if raw is None:
            logger.debug("Redis GET  key=%s  → MISS", key)
            return None
        ttl = r.ttl(key)
        logger.debug("Redis GET  key=%s  → HIT  (ttl=%ss, payload_len=%d)", key, ttl, len(raw))
        result = GenerateTestResponse.model_validate_json(raw)
        logger.debug("Redis GET  key=%s  → deserialised OK  (test_id=%s, questions=%d)",
                     key, result.test_id, len(result.questions))
        return result
    except Exception as exc:
        logger.warning("Redis GET  key=%s  → ERROR: %s", key, exc, exc_info=True)
        return None


def cache_set_test(r: redis.Redis, test: GenerateTestResponse) -> None:
    """
    Store a GenerateTestResponse in Redis with a 24-hour TTL.
    Errors are logged but never raised – the cache is best-effort.
    """
    key = _key(test.test_id)
    logger.debug("Redis SET  key=%s  ttl=%ss  questions=%d",
                 key, TEST_TTL_SECONDS, len(test.questions))
    try:
        payload = test.model_dump_json()
        logger.debug("Redis SET  key=%s  payload_len=%d", key, len(payload))
        result = r.setex(key, TEST_TTL_SECONDS, payload)
        if result:
            logger.info("Redis SET  key=%s  → OK  (ttl=%ss)", key, TEST_TTL_SECONDS)
        else:
            logger.warning("Redis SET  key=%s  → returned falsy: %r", key, result)
    except Exception as exc:
        logger.warning("Redis SET  key=%s  → ERROR: %s", key, exc, exc_info=True)
