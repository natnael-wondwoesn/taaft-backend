# Redis Caching Implementation

This document provides details on the Redis caching implementation for the TAAFT backend, which is used to improve response times for frequently accessed endpoints.

## Overview

The Redis caching system provides a simple way to cache the results of expensive database queries or API calls. It's particularly useful for the tools endpoints, which may involve complex database queries or external API calls.

## Features

- Automatic caching of function results
- Configurable cache TTL (Time To Live)
- Cache invalidation on data updates
- Support for complex data types through JSON serialization
- Automatic key generation based on function arguments

## Configuration

Redis caching can be configured using environment variables:

```
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your_password
REDIS_USERNAME=default
REDIS_CACHE_ENABLED=true
REDIS_CACHE_TTL=300
```

- `REDIS_URL`: The URL of the Redis server (default: `redis://localhost:6379`)
- `REDIS_PASSWORD`: The password for the Redis server (optional)
- `REDIS_USERNAME`: The username for the Redis server (default: `default`)
- `REDIS_CACHE_ENABLED`: Whether to enable Redis caching (default: `true`)
- `REDIS_CACHE_TTL`: The default cache TTL in seconds (default: `300` - 5 minutes)

## Usage

### Decorating Functions

To cache a function, simply decorate it with the `redis_cache` decorator:

```python
from app.services.redis_cache import redis_cache

@redis_cache(prefix="my_function")
async def my_function(param1, param2):
    # Expensive operation
    return result
```

The `prefix` parameter is used to identify the cache keys for this function. It should be unique for each function.

You can also specify a custom TTL for the cache:

```python
@redis_cache(prefix="my_function", ttl=60)  # 60 seconds TTL
async def my_function(param1, param2):
    # Expensive operation
    return result
```

### Invalidating Cache

When data is updated, you should invalidate the relevant cache entries to ensure that subsequent requests get the updated data:

```python
from app.services.redis_cache import invalidate_cache

# Invalidate all cache entries with the given prefix
invalidate_cache("my_function")

# Invalidate specific cache entries with a pattern
invalidate_cache("my_function", pattern="specific_pattern*")
```

## Implementation Details

### Cache Key Generation

Cache keys are generated based on the function name, prefix, and arguments. The key format is:

```
taaft:{prefix}:{hash}
```

Where `{hash}` is an MD5 hash of the function arguments, to ensure that the key is not too long.

### Data Serialization

Function results are serialized to JSON before being stored in Redis. This allows complex data types to be cached, but it also means that non-serializable objects cannot be cached directly.

For non-serializable objects, the `default=str` parameter is used to convert them to strings.

## Cached Endpoints

The following endpoints are currently cached:

### Tools Service

- `get_tools`: List of tools with pagination, filtering, and sorting
- `get_tool_by_id`: Get a tool by its UUID
- `get_tool_by_unique_id`: Get a tool by its unique_id
- `search_tools`: Search for tools by name or description
- `keyword_search_tools`: Search for tools by keywords
- `get_keywords`: Get a list of keywords with their frequency
- `get_tool_with_favorite_status`: Get a tool with its favorite status for a specific user

### Public Routes

- `list_public_tools`: List of public tools
- `get_featured_tools`: List of featured tools
- `get_sponsored_tools`: List of sponsored tools

## Testing

Two test scripts are provided to verify the Redis caching implementation:

1. `test_redis_cache.py`: Basic tests for the Redis cache service
2. `test_tools_redis_cache.py`: Tests specifically for the tools endpoints
3. `load_test_tools_cache.py`: Load tests to demonstrate the performance benefits of Redis caching

To run the tests:

```bash
python test_redis_cache.py
python test_tools_redis_cache.py
python load_test_tools_cache.py
```

The load test script also generates a chart showing the performance improvement with Redis caching.

## Performance Impact

Redis caching can significantly improve response times for frequently accessed endpoints. The exact improvement depends on the complexity of the operation being cached, but it's common to see 10-100x improvements for database-heavy operations.

The load test script provides detailed performance metrics for the tools endpoints.

## Troubleshooting

If Redis caching is not working as expected, check the following:

1. Make sure Redis is running and accessible
2. Check the environment variables to ensure Redis caching is enabled
3. Check the logs for any Redis-related errors
4. Try manually connecting to Redis to verify connectivity:
   ```python
   import redis
   r = redis.from_url("redis://localhost:6379")
   r.ping()  # Should return True
   ```

## Best Practices

1. Use a short TTL for data that changes frequently
2. Use a longer TTL for data that rarely changes
3. Always invalidate the cache when data is updated
4. Be careful with large objects, as they can consume a lot of memory in Redis
5. Monitor Redis memory usage to ensure it doesn't grow too large 