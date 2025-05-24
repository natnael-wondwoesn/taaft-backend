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
    """Test if get_tools function is properly cached and returns ToolResponse objects"""
    logger.info("\nTesting tools list caching...")

    # First call - should hit the database
    start_time = time.time()
    first_result = await get_tools(limit=10)
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Check that we got ToolResponse objects
    if first_result and len(first_result) > 0:
        logger.info(f"First result type: {type(first_result[0]).__name__}")

    # Second call with same parameters - should hit the cache
    start_time = time.time()
    second_result = await get_tools(limit=10)
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check that we still got ToolResponse objects from cache
    if second_result and len(second_result) > 0:
        logger.info(f"Second result type: {type(second_result[0]).__name__}")

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
    """Test if get_tool_by_id function is properly cached and returns a ToolResponse object"""
    logger.info("\nTesting tool_by_id caching...")

    # Get a tool ID to test with
    tools = await get_tools(limit=1)
    if not tools or len(tools) == 0:
        logger.error("No tools found to test with")
        return False

    tool_id = UUID(tools[0].id)
    logger.info(f"Testing with tool ID: {tool_id}")

    # First call - should hit the database
    start_time = time.time()
    first_result = await get_tool_by_id(tool_id)
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Check that we got a ToolResponse object
    if first_result:
        logger.info(f"First result type: {type(first_result).__name__}")

    # Second call with same parameters - should hit the cache
    start_time = time.time()
    second_result = await get_tool_by_id(tool_id)
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check that we still got a ToolResponse object from cache
    if second_result:
        logger.info(f"Second result type: {type(second_result).__name__}")

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
    """Test if search_tools function is properly cached and returns ToolResponse objects"""
    logger.info("\nTesting search_tools caching...")

    # First call - should hit the database
    start_time = time.time()
    first_result = await search_tools(query="ai", limit=10)
    first_execution_time = time.time() - start_time
    logger.info(f"First call execution time: {first_execution_time:.4f}s")

    # Check that we got ToolResponse objects
    if first_result and len(first_result) > 0:
        logger.info(f"First result type: {type(first_result[0]).__name__}")

    # Second call with same parameters - should hit the cache
    start_time = time.time()
    second_result = await search_tools(query="ai", limit=10)
    second_execution_time = time.time() - start_time
    logger.info(f"Second call execution time: {second_execution_time:.4f}s")

    # Check that we still got ToolResponse objects from cache
    if second_result and len(second_result) > 0:
        logger.info(f"Second result type: {type(second_result[0]).__name__}")

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
    """Test if cache invalidation works properly"""
    logger.info("\nTesting cache invalidation...")

    # First call to populate cache
    await get_tools(limit=5)

    # Check if keys exist in Redis
    keys_before = redis_client.keys("taaft:tools_list*")
    logger.info(f"Keys in cache before invalidation: {len(keys_before)}")

    # Invalidate cache
    invalidate_cache("tools_list")

    # Check if keys were removed
    keys_after = redis_client.keys("taaft:tools_list*")
    logger.info(f"Keys in cache after invalidation: {len(keys_after)}")

    # Verify that cache was invalidated
    if len(keys_before) > 0 and len(keys_after) == 0:
        logger.info("Cache invalidation successful")
        return True
    else:
        logger.error("Cache invalidation failed")
        return False


async def main():
    """Run all tests"""
    logger.info("Starting Redis cache tests...")

    # Run tests
    tools_list_result = await test_tools_list_caching()
    tool_by_id_result = await test_tool_by_id_caching()
    search_tools_result = await test_search_tools_caching()
    cache_invalidation_result = await test_cache_invalidation()

    # Print summary
    logger.info("\nTest Results:")
    logger.info(f"Tools List Caching: {'PASS' if tools_list_result else 'FAIL'}")
    logger.info(f"Tool By ID Caching: {'PASS' if tool_by_id_result else 'FAIL'}")
    logger.info(f"Search Tools Caching: {'PASS' if search_tools_result else 'FAIL'}")
    logger.info(
        f"Cache Invalidation: {'PASS' if cache_invalidation_result else 'FAIL'}"
    )

    # Overall result
    all_passed = all(
        [
            tools_list_result,
            tool_by_id_result,
            search_tools_result,
            cache_invalidation_result,
        ]
    )
    logger.info(f"\nOverall Result: {'PASS' if all_passed else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
