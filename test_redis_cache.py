import asyncio
import time
import os
from dotenv import load_dotenv
from app.services.redis_cache import redis_client, redis_cache, invalidate_cache
from app.logger import logger

# Load environment variables
load_dotenv()

# Configure Redis for testing
os.environ["REDIS_CACHE_ENABLED"] = "true"
os.environ["REDIS_CACHE_TTL"] = "10"  # Short TTL for testing


# Test function with Redis caching
@redis_cache(prefix="test_function")
async def test_cached_function(param1, param2):
    """Test function that simulates a slow database query"""
    logger.info(f"Executing test_cached_function with params: {param1}, {param2}")
    # Simulate a slow operation
    await asyncio.sleep(1)
    return {"result": f"Data for {param1} and {param2}", "timestamp": time.time()}


# Test function for cache invalidation
@redis_cache(prefix="invalidation_test")
async def test_invalidation_function(param):
    """Test function for cache invalidation"""
    logger.info(f"Executing test_invalidation_function with param: {param}")
    await asyncio.sleep(0.5)
    return {"result": f"Data for {param}", "timestamp": time.time()}


async def test_redis_connection():
    """Test if Redis connection is working"""
    if not redis_client:
        logger.error("Redis client is not initialized")
        return False

    try:
        redis_client.ping()
        logger.info("Redis connection test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Redis connection test: FAILED - {str(e)}")
        return False


async def test_cache_hit():
    """Test if cache hit is working correctly"""
    # First call - should execute the function
    start_time = time.time()
    first_result = await test_cached_function("test1", "test2")
    first_execution_time = time.time() - start_time

    # Second call with same parameters - should retrieve from cache
    start_time = time.time()
    second_result = await test_cached_function("test1", "test2")
    second_execution_time = time.time() - start_time

    # Check if timestamps are the same (indicating cache hit)
    if first_result["timestamp"] == second_result["timestamp"]:
        logger.info("Cache hit test: SUCCESS")
        logger.info(f"First execution time: {first_execution_time:.4f}s")
        logger.info(f"Second execution time: {second_execution_time:.4f}s")
        logger.info(
            f"Speed improvement: {first_execution_time/second_execution_time:.2f}x"
        )
        return True
    else:
        logger.error("Cache hit test: FAILED - Different results returned")
        return False


async def test_cache_expiration():
    """Test if cache expiration is working correctly"""
    # First call
    first_result = await test_cached_function("expire1", "expire2")
    logger.info("First call completed, waiting for TTL expiration...")

    # Wait for TTL to expire (TTL is set to 10 seconds)
    await asyncio.sleep(11)

    # Call again after TTL expired
    second_result = await test_cached_function("expire1", "expire2")

    # Check if timestamps are different (indicating cache expiration)
    if first_result["timestamp"] != second_result["timestamp"]:
        logger.info("Cache expiration test: SUCCESS")
        return True
    else:
        logger.error("Cache expiration test: FAILED - Cache did not expire")
        return False


async def test_cache_invalidation():
    """Test if cache invalidation is working correctly"""
    # First call
    first_result = await test_invalidation_function("invalidate_test")

    # Invalidate the cache
    invalidate_cache("invalidation_test")
    logger.info("Cache invalidated")

    # Second call after invalidation
    second_result = await test_invalidation_function("invalidate_test")

    # Check if timestamps are different (indicating successful invalidation)
    if first_result["timestamp"] != second_result["timestamp"]:
        logger.info("Cache invalidation test: SUCCESS")
        return True
    else:
        logger.error("Cache invalidation test: FAILED - Cache was not invalidated")
        return False


async def test_different_params():
    """Test if different parameters create different cache entries"""
    # Call with first set of parameters
    result1 = await test_cached_function("param1", "param2")

    # Call with different parameters
    result2 = await test_cached_function("param3", "param4")

    # Both should execute the function (not hit cache)
    if result1["timestamp"] != result2["timestamp"]:
        logger.info("Different parameters test: SUCCESS")
        return True
    else:
        logger.error(
            "Different parameters test: FAILED - Same result returned for different params"
        )
        return False


async def run_tests():
    """Run all Redis cache tests"""
    logger.info("Starting Redis cache tests...")

    # Test Redis connection
    if not await test_redis_connection():
        logger.error("Redis connection failed, skipping remaining tests")
        return

    # Run the tests
    tests = [
        ("Cache Hit Test", test_cache_hit()),
        ("Different Parameters Test", test_different_params()),
        ("Cache Invalidation Test", test_cache_invalidation()),
        ("Cache Expiration Test", test_cache_expiration()),
    ]

    # Execute tests and collect results
    results = []
    for test_name, test_coro in tests:
        logger.info(f"\nRunning {test_name}...")
        result = await test_coro
        results.append((test_name, result))

    # Print summary
    logger.info("\n===== TEST RESULTS =====")
    all_passed = True
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False

    if all_passed:
        logger.info("\nAll tests PASSED!")
    else:
        logger.error("\nSome tests FAILED!")


if __name__ == "__main__":
    # Run the tests
    asyncio.run(run_tests())
