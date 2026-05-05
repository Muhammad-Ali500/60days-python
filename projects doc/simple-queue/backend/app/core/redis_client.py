import redis
from app.core.config import settings

# Single shared Redis client for caching
# Celery uses its own connection internally (different DB indices)
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis():
    """FastAPI dependency — yields the redis client."""
    return redis_client
