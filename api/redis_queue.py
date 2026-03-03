"""
Redis client and queue management for async tasks.
Used for search queue mode and export processing.
"""

import json
import os
import logging
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5,
    )
    redis_client.ping()
    logger.info("Redis connected")
except redis.ConnectionError:
    logger.warning("Redis not available — queue and cache features will be limited")
    redis_client = None  # type: ignore


# ─── Queue Operations ──────────────────────────────────

def enqueue_task(task_data: dict) -> bool:
    """Add a task to the processing queue."""
    if not redis_client:
        return False
    try:
        redis_client.rpush("fila_consultas", json.dumps(task_data))
        return True
    except redis.RedisError as e:
        logger.error(f"Redis enqueue failed: {e}")
        return False


def dequeue_task() -> Optional[dict]:
    """Pop the next task from the queue."""
    if not redis_client:
        return None
    try:
        raw = redis_client.lpop("fila_consultas")
        if raw:
            return json.loads(raw)
    except redis.RedisError as e:
        logger.error(f"Redis dequeue failed: {e}")
    return None


def get_queue_size() -> int:
    """Return current queue length."""
    if not redis_client:
        return 0
    try:
        return redis_client.llen("fila_consultas")  # type: ignore
    except redis.RedisError as e:
        logger.error(f"Redis llen failed: {e}")
        return 0


def clear_queue() -> int:
    """Clear the entire queue. Returns number of items removed."""
    if not redis_client:
        return 0
    try:
        size = get_queue_size()
        redis_client.delete("fila_consultas")
        return size
    except redis.RedisError as e:
        logger.error(f"Redis clear failed: {e}")
        return 0


# ─── Task Status Tracking ──────────────────────────────

def set_task_status(task_id: str, data: dict, ttl: int = 86400):
    """Save task status/result in Redis with TTL (default 24h)."""
    if not redis_client:
        return
    try:
        redis_client.setex(f"task:{task_id}", ttl, json.dumps(data))
    except redis.RedisError as e:
        logger.error(f"Redis set_task_status failed: {e}")


def get_task_status(task_id: str) -> Optional[dict]:
    """Retrieve task status by ID."""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"task:{task_id}")
        if raw:
            return json.loads(raw)
    except redis.RedisError as e:
        logger.error(f"Redis get_task_status failed: {e}")
    return None


# ─── Cache Operations ──────────────────────────────────

# ─── ETL Progress ──────────────────────────────────────

ETL_PROGRESS_KEY = "etl:progress"
ETL_PROGRESS_CHANNEL = "etl:progress:updates"

def etl_progress_set(data: dict, ttl: int = 86400):
    """Store ETL progress state and publish to Pub/Sub channel."""
    if not redis_client:
        return
    try:
        payload = json.dumps(data)
        redis_client.setex(ETL_PROGRESS_KEY, ttl, payload)
        redis_client.publish(ETL_PROGRESS_CHANNEL, payload)
    except redis.RedisError as e:
        logger.error(f"Redis etl_progress_set failed: {e}")


def etl_progress_get() -> Optional[dict]:
    """Retrieve current ETL progress."""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(ETL_PROGRESS_KEY)
        if raw:
            return json.loads(raw)
    except redis.RedisError as e:
        logger.error(f"Redis etl_progress_get failed: {e}")
    return None


def etl_progress_clear():
    """Remove ETL progress key."""
    if not redis_client:
        return
    try:
        redis_client.delete(ETL_PROGRESS_KEY)
    except redis.RedisError as e:
        logger.error(f"Redis etl_progress_clear failed: {e}")


def cache_set(key: str, value: Any, ttl: int = 300):
    """Set a cache entry with TTL (default 5 minutes)."""
    if not redis_client:
        return
    try:
        redis_client.setex(f"cache:{key}", ttl, json.dumps(value))
    except redis.RedisError as e:
        logger.error(f"Redis cache_set failed: {e}")


def cache_get(key: str) -> Optional[Any]:
    """Get a value from cache."""
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"cache:{key}")
        if raw:
            return json.loads(raw)
    except redis.RedisError as e:
        logger.error(f"Redis cache_get failed: {e}")
    return None


def cache_clear_all() -> int:
    """Clear all cache entries. Returns count of keys deleted."""
    if not redis_client:
        return 0
    try:
        keys = redis_client.keys("cache:*")
        if keys:
            return redis_client.delete(*keys)
    except redis.RedisError as e:
        logger.error(f"Redis cache_clear failed: {e}")
    return 0
