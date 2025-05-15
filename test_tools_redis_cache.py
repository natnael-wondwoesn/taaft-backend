import asyncio
import time
import os
import json
from dotenv import load_dotenv
from app.services.redis_cache import redis_client, invalidate_cache
from app.tools.tools_service import (
    get_tools,
    get_tool_by_id,
    search_tools,
    keyword_search_tools,
)
from app.logger import logger
from uuid import UUID

# Load environment variables
load_dotenv()

# Configure Redis for testing
os.environ["REDIS_CACHE_ENABLED"] = "true"
os.environ["REDIS_CACHE_TTL"] = "30"  # 30 seconds TTL for testing


async def test_tools_list_caching():
    """Test if get_tools function is properly cached"""
    logger.info("\nTesting tools list caching...")

    # First call - should hit the database
    start_time = time.time()
    first_result = await get_tools(limit=10)
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Second call with same parameters - should hit the cache
    start_time = time.time()
    second_result = await get_tools(limit=10)
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check if the second call was faster (cache hit)
    if second_execution_time < first_execution_time:
        logger.info(
            f"Cache hit confirmed! Speed improvement: {first_execution_time/second_execution_time:.2f}x"
        )
        return True
    else:
        logger.error("Cache miss or no performance improvement")
        return False


async def test_tool_by_id_caching():
    """Test if get_tool_by_id function is properly cached"""
    logger.info("\nTesting tool by ID caching...")

    # Get a tool ID from the list first
    tools = await get_tools(limit=1)
    if not tools or len(tools) == 0:
        logger.error("No tools found to test with")
        return False

    tool_id = tools[0].id

    # First call - should hit the database
    start_time = time.time()
    first_result = await get_tool_by_id(UUID(tool_id))
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Second call with same ID - should hit the cache
    start_time = time.time()
    second_result = await get_tool_by_id(UUID(tool_id))
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check if the second call was faster (cache hit)
    if second_execution_time < first_execution_time:
        logger.info(
            f"Cache hit confirmed! Speed improvement: {first_execution_time/second_execution_time:.2f}x"
        )
        return True
    else:
        logger.error("Cache miss or no performance improvement")
        return False


async def test_search_tools_caching():
    """Test if search_tools function is properly cached"""
    logger.info("\nTesting search tools caching...")

    search_query = "ai"  # Generic search term that should match some tools

    # First call - should hit the database/search engine
    start_time = time.time()
    first_result = await search_tools(query=search_query, limit=5)
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Second call with same search query - should hit the cache
    start_time = time.time()
    second_result = await search_tools(query=search_query, limit=5)
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check if the second call was faster (cache hit)
    if second_execution_time < first_execution_time:
        logger.info(
            f"Cache hit confirmed! Speed improvement: {first_execution_time/second_execution_time:.2f}x"
        )
        return True
    else:
        logger.error("Cache miss or no performance improvement")
        return False


async def test_keyword_search_caching():
    """Test if keyword_search_tools function is properly cached"""
    logger.info("\nTesting keyword search caching...")

    keywords = ["ai", "tool"]

    # First call - should hit the database
    start_time = time.time()
    first_result = await keyword_search_tools(keywords=keywords, limit=5)
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Second call with same keywords - should hit the cache
    start_time = time.time()
    second_result = await keyword_search_tools(keywords=keywords, limit=5)
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check if the second call was faster (cache hit)
    if second_execution_time < first_execution_time:
        logger.info(
            f"Cache hit confirmed! Speed improvement: {first_execution_time/second_execution_time:.2f}x"
        )
        return True
    else:
        logger.error("Cache miss or no performance improvement")
        return False


async def test_cache_invalidation():
    """Test if cache invalidation works for tools endpoints"""
    logger.info("\nTesting cache invalidation for tools...")

    # First call to get_tools - should hit the database
    first_result = await get_tools(limit=5)

    # Invalidate the cache
    invalidate_cache("tools_list")
    logger.info("Cache invalidated for tools_list")

    # Second call - should hit the database again
    start_time = time.time()
    second_result = await get_tools(limit=5)
    second_execution_time = time.time() - start_time

    # Third call - should hit the cache
    start_time = time.time()
    third_result = await get_tools(limit=5)
    third_execution_time = time.time() - start_time

    # Check if the third call was faster than the second (indicating second call was a cache miss)
    if third_execution_time < second_execution_time:
        logger.info(
            f"Cache invalidation confirmed! Third call was faster: {third_execution_time:.4f}s vs {second_execution_time:.4f}s"
        )
        return True
    else:
        logger.error("Cache invalidation test failed or no performance difference")
        return False


async def test_redis_keys():
    """Test if Redis keys are created with the expected prefixes"""
    logger.info("\nTesting Redis keys for tools endpoints...")

    if not redis_client:
        logger.error("Redis client is not initialized")
        return False

    # Clear any existing keys with these prefixes
    for prefix in [
        "taaft:tools_list",
        "taaft:tool_by_id",
        "taaft:search_tools",
        "taaft:keyword_search",
    ]:
        keys = redis_client.keys(f"{prefix}*")
        if keys:
            redis_client.delete(*keys)

    # Make calls to create cache entries
    await get_tools(limit=3)
    tools = await get_tools(limit=1)
    if tools and len(tools) > 0:
        await get_tool_by_id(UUID(tools[0].id))
    await search_tools(query="ai", limit=3)
    await keyword_search_tools(keywords=["ai"], limit=3)

    # Check if keys were created with the expected prefixes
    tools_list_keys = redis_client.keys("taaft:tools_list*")
    tool_by_id_keys = redis_client.keys("taaft:tool_by_id*")
    search_tools_keys = redis_client.keys("taaft:search_tools*")
    keyword_search_keys = redis_client.keys("taaft:keyword_search*")

    logger.info(f"Found {len(tools_list_keys)} tools_list keys")
    logger.info(f"Found {len(tool_by_id_keys)} tool_by_id keys")
    logger.info(f"Found {len(search_tools_keys)} search_tools keys")
    logger.info(f"Found {len(keyword_search_keys)} keyword_search keys")

    # Check if all types of keys were created
    all_keys_found = (
        len(tools_list_keys) > 0
        and len(tool_by_id_keys) > 0
        and len(search_tools_keys) > 0
        and len(keyword_search_keys) > 0
    )

    if all_keys_found:
        logger.info("All expected Redis key types were found")
        return True
    else:
        logger.error("Some expected Redis key types were not found")
        return False


async def run_tests():
    """Run all tools Redis cache tests"""
    logger.info("Starting tools Redis cache tests...")

    # Check if Redis is available
    if not redis_client:
        logger.error("Redis client is not initialized, skipping tests")
        return

    try:
        redis_client.ping()
    except Exception as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return

    # Run the tests
    tests = [
        ("Tools List Caching", test_tools_list_caching()),
        ("Tool By ID Caching", test_tool_by_id_caching()),
        ("Search Tools Caching", test_search_tools_caching()),
        ("Keyword Search Caching", test_keyword_search_caching()),
        ("Cache Invalidation", test_cache_invalidation()),
        ("Redis Keys Check", test_redis_keys()),
    ]

    # Execute tests and collect results
    results = []
    for test_name, test_coro in tests:
        logger.info(f"\nRunning {test_name}...")
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))

    # Print summary
    logger.info("\n===== TOOLS CACHE TEST RESULTS =====")
    all_passed = True
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if not result:
            all_passed = False

    if all_passed:
        logger.info("\nAll tools cache tests PASSED!")
    else:
        logger.error("\nSome tools cache tests FAILED!")


if __name__ == "__main__":
    # Run the tests
    asyncio.run(run_tests())
