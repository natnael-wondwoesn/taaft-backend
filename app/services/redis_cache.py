import json
import os
from typing import Any, Optional, Union, Dict, Type
import redis
from ..logger import logger
from functools import wraps
import hashlib
import inspect
import asyncio
from pydantic import BaseModel

# Get Redis configuration from environment variables
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_CACHE_ENABLED = os.getenv("REDIS_CACHE_ENABLED", "true").lower() == "true"
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "300"))  # Default 5 minutes
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")

# Initialize Redis client
try:
    redis_client = (
        redis.Redis(
            host="redis-13784.c8.us-east-1-2.ec2.redns.redis-cloud.com",
            port=13784,
            password=REDIS_PASSWORD,
            username=REDIS_USERNAME,
            decode_responses=True,
        )
        if REDIS_CACHE_ENABLED
        else None
    )

    if REDIS_CACHE_ENABLED:
        # Test connection
        redis_client.ping()
        logger.info("Redis connection established successfully")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {str(e)}")
    redis_client = None
    REDIS_CACHE_ENABLED = False


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a unique cache key based on function arguments
    """
    # Convert args and kwargs to strings and join them
    args_str = "_".join([str(arg) for arg in args])
    kwargs_str = "_".join([f"{k}:{v}" for k, v in sorted(kwargs.items())])

    # Combine prefix with args and kwargs
    key_base = f"{prefix}:{args_str}:{kwargs_str}"

    # Create a hash of the key to ensure it's not too long
    key_hash = hashlib.md5(key_base.encode()).hexdigest()
    return f"taaft:{prefix}:{key_hash}"


class PydanticJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Pydantic models and other special types"""

    def default(self, obj):
        # Handle Pydantic models
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        # Handle other types that need special serialization
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def serialize_for_cache(obj: Any) -> str:
    """Serialize an object for caching, handling Pydantic models properly"""
    try:
        return json.dumps(obj, cls=PydanticJSONEncoder)
    except Exception as e:
        logger.error(f"Error serializing object for cache: {str(e)}")
        # Fallback to string representation
        return json.dumps(str(obj))


def deserialize_from_cache(data: str, return_type_hint: Optional[Type] = None) -> Any:
    """
    Deserialize data from cache, reconstructing Pydantic models if needed

    Args:
        data: The JSON string from cache
        return_type_hint: Optional type hint for the return value

    Returns:
        Deserialized object, possibly reconstructed as a Pydantic model
    """
    try:
        # First parse the JSON
        parsed_data = json.loads(data)

        # If we have a type hint and it's a Pydantic model, try to reconstruct it
        if return_type_hint and issubclass(return_type_hint, BaseModel):
            # Handle list of models
            if (
                isinstance(parsed_data, list)
                and hasattr(return_type_hint, "__origin__")
                and return_type_hint.__origin__ is list
            ):
                # Get the type of items in the list
                item_type = return_type_hint.__args__[0]
                if issubclass(item_type, BaseModel):
                    return [item_type(**item) for item in parsed_data]

            # Handle single model
            return return_type_hint(**parsed_data)

        # For other types, return the parsed data as is
        return parsed_data
    except Exception as e:
        logger.error(f"Error deserializing from cache: {str(e)}")
        # Return the parsed data as is if reconstruction fails
        return json.loads(data)


def redis_cache(prefix: str, ttl: int = REDIS_CACHE_TTL):
    """
    Decorator to cache function results in Redis

    Args:
        prefix: Prefix for the cache key
        ttl: Time to live in seconds (default: 300 seconds / 5 minutes)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not REDIS_CACHE_ENABLED or not redis_client:
                # If Redis is not enabled, just call the function
                return await func(*args, **kwargs)

            # Generate a unique cache key
            cache_key = generate_cache_key(prefix, *args, **kwargs)

            # Try to get cached result
            cached_result = redis_client.get(cache_key)

            if cached_result:
                try:
                    # Get return type hint if available
                    return_type_hint = None
                    signature = inspect.signature(func)
                    if signature.return_annotation != inspect.Signature.empty:
                        return_type_hint = signature.return_annotation

                    # Return cached result if available, properly deserialized
                    logger.info(f"Cache hit for {func.__name__} with key {cache_key}")
                    return deserialize_from_cache(cached_result, return_type_hint)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode cached result for {cache_key}")

            # If no cached result or decoding failed, call the function
            result = await func(*args, **kwargs)

            # Cache the result
            try:
                # Use custom serialization to handle Pydantic models
                serialized_result = serialize_for_cache(result)
                redis_client.setex(cache_key, ttl, serialized_result)
                logger.info(f"Cached result for {func.__name__} with key {cache_key}")
            except Exception as e:
                logger.error(f"Failed to cache result for {cache_key}: {str(e)}")

            return result

        return wrapper

    return decorator


def invalidate_cache(prefix: str, pattern: str = "*"):
    """
    Invalidate cache entries matching the given prefix and pattern

    Args:
        prefix: Cache key prefix
        pattern: Pattern to match (default: "*" to match all)
    """
    if not REDIS_CACHE_ENABLED or not redis_client:
        return

    try:
        # Find all keys matching the pattern
        keys = redis_client.keys(f"taaft:{prefix}:{pattern}")

        # Delete the keys if any found
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache entries with prefix {prefix}")
    except Exception as e:
        logger.error(f"Failed to invalidate cache for prefix {prefix}: {str(e)}")
