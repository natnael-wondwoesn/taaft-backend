import asyncio
import time
import os
import statistics
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from app.services.redis_cache import redis_client, invalidate_cache
from app.tools.tools_service import get_tools, search_tools, keyword_search_tools
from app.logger import logger

# Load environment variables
load_dotenv()

# Configure Redis for testing
os.environ["REDIS_CACHE_ENABLED"] = "true"
os.environ["REDIS_CACHE_TTL"] = "300"  # 5 minutes TTL

# Number of requests to make for each test
NUM_REQUESTS = 50


async def measure_performance(func, *args, **kwargs):
    """Measure the performance of a function call"""
    start_time = time.time()
    result = await func(*args, **kwargs)
    execution_time = time.time() - start_time
    return execution_time, result


async def load_test_get_tools(with_cache=True):
    """Load test the get_tools function with or without cache"""
    # Clear cache if testing without cache
    if not with_cache and redis_client:
        keys = redis_client.keys("taaft:tools_list*")
        if keys:
            redis_client.delete(*keys)

    # Parameters for the test
    limit = 10
    skip = 0

    # Run the test
    execution_times = []
    for i in range(NUM_REQUESTS):
        execution_time, _ = await measure_performance(get_tools, skip=skip, limit=limit)
        execution_times.append(execution_time)

        # Clear cache between requests if testing without cache
        if not with_cache and redis_client:
            keys = redis_client.keys("taaft:tools_list*")
            if keys:
                redis_client.delete(*keys)

    return execution_times


async def load_test_search_tools(with_cache=True):
    """Load test the search_tools function with or without cache"""
    # Clear cache if testing without cache
    if not with_cache and redis_client:
        keys = redis_client.keys("taaft:search_tools*")
        if keys:
            redis_client.delete(*keys)

    # Parameters for the test
    search_queries = ["ai", "tool", "generator", "assistant", "free"]
    limit = 5

    # Run the test
    execution_times = []
    for i in range(NUM_REQUESTS):
        # Rotate through search queries
        query = search_queries[i % len(search_queries)]

        execution_time, _ = await measure_performance(
            search_tools, query=query, limit=limit
        )
        execution_times.append(execution_time)

        # Clear cache between requests if testing without cache
        if not with_cache and redis_client:
            keys = redis_client.keys("taaft:search_tools*")
            if keys:
                redis_client.delete(*keys)

    return execution_times


async def load_test_keyword_search(with_cache=True):
    """Load test the keyword_search_tools function with or without cache"""
    # Clear cache if testing without cache
    if not with_cache and redis_client:
        keys = redis_client.keys("taaft:keyword_search*")
        if keys:
            redis_client.delete(*keys)

    # Parameters for the test
    keyword_sets = [
        ["ai", "tool"],
        ["free", "generator"],
        ["writing", "assistant"],
        ["image", "creation"],
        ["code", "helper"],
    ]
    limit = 5

    # Run the test
    execution_times = []
    for i in range(NUM_REQUESTS):
        # Rotate through keyword sets
        keywords = keyword_sets[i % len(keyword_sets)]

        execution_time, _ = await measure_performance(
            keyword_search_tools, keywords=keywords, limit=limit
        )
        execution_times.append(execution_time)

        # Clear cache between requests if testing without cache
        if not with_cache and redis_client:
            keys = redis_client.keys("taaft:keyword_search*")
            if keys:
                redis_client.delete(*keys)

    return execution_times


def print_statistics(title, with_cache_times, without_cache_times):
    """Print statistics for the test results"""
    logger.info(f"\n===== {title} =====")

    # With cache statistics
    with_cache_avg = statistics.mean(with_cache_times)
    with_cache_min = min(with_cache_times)
    with_cache_max = max(with_cache_times)
    with_cache_median = statistics.median(with_cache_times)

    # Without cache statistics
    without_cache_avg = statistics.mean(without_cache_times)
    without_cache_min = min(without_cache_times)
    without_cache_max = max(without_cache_times)
    without_cache_median = statistics.median(without_cache_times)

    # Performance improvement
    improvement_factor = without_cache_avg / with_cache_avg

    logger.info(f"With Cache:")
    logger.info(f"  Average: {with_cache_avg:.4f}s")
    logger.info(f"  Minimum: {with_cache_min:.4f}s")
    logger.info(f"  Maximum: {with_cache_max:.4f}s")
    logger.info(f"  Median:  {with_cache_median:.4f}s")

    logger.info(f"Without Cache:")
    logger.info(f"  Average: {without_cache_avg:.4f}s")
    logger.info(f"  Minimum: {without_cache_min:.4f}s")
    logger.info(f"  Maximum: {without_cache_max:.4f}s")
    logger.info(f"  Median:  {without_cache_median:.4f}s")

    logger.info(f"Performance Improvement: {improvement_factor:.2f}x faster with cache")

    return {
        "with_cache": {
            "avg": with_cache_avg,
            "min": with_cache_min,
            "max": with_cache_max,
            "median": with_cache_median,
        },
        "without_cache": {
            "avg": without_cache_avg,
            "min": without_cache_min,
            "max": without_cache_max,
            "median": without_cache_median,
        },
        "improvement_factor": improvement_factor,
    }


def plot_results(results):
    """Plot the test results"""
    try:
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Plot average execution times
        endpoints = list(results.keys())
        with_cache_avgs = [
            results[endpoint]["with_cache"]["avg"] for endpoint in endpoints
        ]
        without_cache_avgs = [
            results[endpoint]["without_cache"]["avg"] for endpoint in endpoints
        ]

        x = np.arange(len(endpoints))
        width = 0.35

        ax1.bar(x - width / 2, with_cache_avgs, width, label="With Cache")
        ax1.bar(x + width / 2, without_cache_avgs, width, label="Without Cache")

        ax1.set_ylabel("Average Execution Time (s)")
        ax1.set_title("Average Execution Time by Endpoint")
        ax1.set_xticks(x)
        ax1.set_xticklabels([ep.replace("_", " ").title() for ep in endpoints])
        ax1.legend()

        # Plot improvement factors
        improvement_factors = [
            results[endpoint]["improvement_factor"] for endpoint in endpoints
        ]

        ax2.bar(x, improvement_factors, width)
        ax2.set_ylabel("Speed Improvement Factor (x)")
        ax2.set_title("Performance Improvement with Redis Cache")
        ax2.set_xticks(x)
        ax2.set_xticklabels([ep.replace("_", " ").title() for ep in endpoints])

        # Add improvement factor labels
        for i, v in enumerate(improvement_factors):
            ax2.text(i, v + 0.5, f"{v:.2f}x", ha="center")

        plt.tight_layout()
        plt.savefig("redis_cache_performance.png")
        logger.info("Performance chart saved to redis_cache_performance.png")
    except Exception as e:
        logger.error(f"Failed to create performance chart: {str(e)}")


async def run_load_tests():
    """Run load tests for Redis caching of tools endpoints"""
    logger.info("Starting Redis cache load tests...")

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
    logger.info(f"\nRunning load tests with {NUM_REQUESTS} requests per test...")

    # Test get_tools
    logger.info("\nTesting get_tools with cache...")
    get_tools_with_cache = await load_test_get_tools(with_cache=True)

    logger.info("\nTesting get_tools without cache...")
    get_tools_without_cache = await load_test_get_tools(with_cache=False)

    # Test search_tools
    logger.info("\nTesting search_tools with cache...")
    search_tools_with_cache = await load_test_search_tools(with_cache=True)

    logger.info("\nTesting search_tools without cache...")
    search_tools_without_cache = await load_test_search_tools(with_cache=False)

    # Test keyword_search_tools
    logger.info("\nTesting keyword_search_tools with cache...")
    keyword_search_with_cache = await load_test_keyword_search(with_cache=True)

    logger.info("\nTesting keyword_search_tools without cache...")
    keyword_search_without_cache = await load_test_keyword_search(with_cache=False)

    # Print statistics
    results = {}
    results["get_tools"] = print_statistics(
        "GET TOOLS PERFORMANCE", get_tools_with_cache, get_tools_without_cache
    )
    results["search_tools"] = print_statistics(
        "SEARCH TOOLS PERFORMANCE", search_tools_with_cache, search_tools_without_cache
    )
    results["keyword_search"] = print_statistics(
        "KEYWORD SEARCH PERFORMANCE",
        keyword_search_with_cache,
        keyword_search_without_cache,
    )

    # Plot the results
    plot_results(results)

    logger.info("\nLoad tests completed!")


if __name__ == "__main__":
    # Run the load tests
    asyncio.run(run_load_tests())
