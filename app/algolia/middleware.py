"""
Response time monitoring and caching middleware for search requests
"""

import time
from typing import Callable, Dict, Any, Optional, List
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from ..logger import logger
import asyncio
import datetime

# Simple in-memory cache for search results
# Structure: { "cache_key": {"data": response_data, "timestamp": timestamp, "ttl": ttl} }
SEARCH_CACHE = {}

# Global stats dictionary to be shared across the application
# Will be exposed through the routes module
SEARCH_PERFORMANCE_STATS = {
    "total_requests": 0,
    "total_response_time": 0,
    "cached_requests": 0,
    "cached_response_time": 0,
    "slow_requests": 0,  # Requests taking more than 1s
    "error_requests": 0,
    "last_reset": datetime.datetime.utcnow(),
}


class SearchPerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to log and monitor search response times"""

    def __init__(self, app, cache_enabled: bool = True, default_ttl: int = 300):
        """
        Initialize the middleware

        Args:
            app: The FastAPI application
            cache_enabled: Whether caching is enabled (default: True)
            default_ttl: Default TTL for cached items in seconds (default: 5 minutes)
        """
        super().__init__(app)
        self.cache_enabled = cache_enabled
        self.default_ttl = default_ttl
        # Initialize response time stats
        self.response_times = []
        self.last_stats_time = time.time()
        self.stats_interval = 60  # Log stats every minute
        logger.info("Search Performance Middleware initialized")

        # Start cache cleanup task
        asyncio.create_task(self._cleanup_cache_periodically())

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and log performance metrics

        Args:
            request: The incoming request
            call_next: The next middleware in the chain

        Returns:
            The response from the next middleware
        """
        # Only process search API requests
        if not self._is_search_request(request.url.path):
            return await call_next(request)

        start_time = time.time()

        # Check if we can serve from cache
        cache_key = None
        if self.cache_enabled and request.method in ["GET", "POST"]:
            cache_key = await self._generate_cache_key(request)
            cached_response = self._get_from_cache(cache_key)

            if cached_response:
                # Update stats for cached response
                elapsed = time.time() - start_time
                self._update_stats(elapsed, True)

                # Update global stats
                self._update_global_stats(elapsed, True, False)

                logger.debug(
                    f"Cache hit for {request.url.path} - served in {elapsed:.4f}s"
                )
                return Response(
                    content=cached_response["data"],
                    media_type="application/json",
                    headers={"X-Cache": "HIT", "X-Response-Time": f"{elapsed:.4f}"},
                )

        # Process the request normally
        try:
            response = await call_next(request)
            is_error = response.status_code >= 400
        except Exception as e:
            # If an exception occurs, log it and update stats
            elapsed = time.time() - start_time
            logger.error(f"Error processing search request: {str(e)}")
            self._update_stats(elapsed, False)
            self._update_global_stats(elapsed, False, True)
            raise

        # Calculate response time
        elapsed = time.time() - start_time
        self._update_stats(elapsed, False)

        # Update global stats
        self._update_global_stats(elapsed, False, is_error)

        # Log slow responses (over 500ms)
        if elapsed > 0.5:
            logger.warning(
                f"Slow search response: {request.url.path} took {elapsed:.4f}s"
            )
        else:
            logger.debug(
                f"Search response: {request.url.path} completed in {elapsed:.4f}s"
            )

        # Add response time header
        response.headers["X-Response-Time"] = f"{elapsed:.4f}"
        response.headers["X-Cache"] = "MISS"

        # Cache the response if appropriate
        if self.cache_enabled and cache_key and 200 <= response.status_code < 300:
            # Get response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            # Create a new response with the same content
            new_response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

            # Cache the response
            ttl = self._get_cache_ttl(request)
            self._add_to_cache(cache_key, response_body, ttl)

            return new_response

        return response

    def _is_search_request(self, path: str) -> bool:
        """
        Check if the request is a search-related request

        Args:
            path: The request path

        Returns:
            True if it's a search request, False otherwise
        """
        search_paths = ["/api/search/", "/api/tools/keyword-search"]
        return any(path.startswith(prefix) for prefix in search_paths)

    async def _generate_cache_key(self, request: Request) -> str:
        """
        Generate a cache key for the request

        Args:
            request: The incoming request

        Returns:
            A string cache key
        """
        # For GET requests, use the full URL as the cache key
        if request.method == "GET":
            return f"{request.method}:{request.url}"

        # For POST requests, include the request body in the cache key
        if request.method == "POST":
            body = await request.body()
            return f"{request.method}:{request.url}:{body.decode('utf-8')}"

        # Default fallback
        return f"{request.method}:{request.url}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a response from the cache

        Args:
            cache_key: The cache key

        Returns:
            The cached response or None if not found/expired
        """
        cache_item = SEARCH_CACHE.get(cache_key)
        if not cache_item:
            return None

        # Check if the item has expired
        now = time.time()
        if now - cache_item["timestamp"] > cache_item["ttl"]:
            # Remove expired item
            del SEARCH_CACHE[cache_key]
            return None

        return cache_item

    def _add_to_cache(self, cache_key: str, data: bytes, ttl: int) -> None:
        """
        Add a response to the cache

        Args:
            cache_key: The cache key
            data: The response data
            ttl: Time-to-live in seconds
        """
        SEARCH_CACHE[cache_key] = {"data": data, "timestamp": time.time(), "ttl": ttl}

    def _get_cache_ttl(self, request: Request) -> int:
        """
        Determine the appropriate TTL for a request

        Args:
            request: The incoming request

        Returns:
            TTL in seconds
        """
        # Different TTLs based on request path
        path = request.url.path

        # Shorter TTL for real-time queries
        if path.endswith("/nlp-search"):
            return 60  # 1 minute

        # Medium TTL for suggestion queries
        if path.endswith("/suggest"):
            return 120  # 2 minutes

        # Longer TTL for more stable content
        if path.endswith("/glossary") or path.endswith("/search-by-category"):
            return 600  # 10 minutes

        # Default TTL
        return self.default_ttl

    def _update_stats(self, elapsed: float, cached: bool) -> None:
        """
        Update response time statistics

        Args:
            elapsed: The response time in seconds
            cached: Whether the response was served from cache
        """
        self.response_times.append((elapsed, cached))

        # Log stats periodically
        now = time.time()
        if now - self.last_stats_time > self.stats_interval:
            self._log_stats()
            self.last_stats_time = now

    def _update_global_stats(
        self, elapsed: float, cached: bool, is_error: bool
    ) -> None:
        """
        Update global search performance statistics

        Args:
            elapsed: The response time in seconds
            cached: Whether the response was served from cache
            is_error: Whether the response had an error
        """
        # Update total requests and response time
        SEARCH_PERFORMANCE_STATS["total_requests"] += 1
        SEARCH_PERFORMANCE_STATS["total_response_time"] += elapsed

        # Update cached requests if applicable
        if cached:
            SEARCH_PERFORMANCE_STATS["cached_requests"] += 1
            SEARCH_PERFORMANCE_STATS["cached_response_time"] += elapsed

        # Update slow requests if applicable (>1s)
        if elapsed > 1.0:
            SEARCH_PERFORMANCE_STATS["slow_requests"] += 1

        # Update error requests if applicable
        if is_error:
            SEARCH_PERFORMANCE_STATS["error_requests"] += 1

    def _log_stats(self) -> None:
        """Log response time statistics"""
        if not self.response_times:
            return

        # Separate cached and non-cached responses
        cached = [t for t, c in self.response_times if c]
        non_cached = [t for t, c in self.response_times if not c]

        # Calculate statistics
        avg_time = sum(t for t, _ in self.response_times) / len(self.response_times)
        avg_cached = sum(cached) / len(cached) if cached else 0
        avg_non_cached = sum(non_cached) / len(non_cached) if non_cached else 0

        # Log statistics
        logger.info(
            f"Search performance stats - "
            f"Avg: {avg_time:.4f}s, "
            f"Cached: {avg_cached:.4f}s ({len(cached)} reqs), "
            f"Non-cached: {avg_non_cached:.4f}s ({len(non_cached)} reqs), "
            f"Total: {len(self.response_times)} requests"
        )

        # Reset stats
        self.response_times = []

    async def _cleanup_cache_periodically(self) -> None:
        """Periodically clean up expired cache entries"""
        while True:
            await asyncio.sleep(60)  # Run every minute
            self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Remove expired items from the cache"""
        now = time.time()
        keys_to_delete = []

        for key, item in SEARCH_CACHE.items():
            if now - item["timestamp"] > item["ttl"]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del SEARCH_CACHE[key]

        if keys_to_delete:
            logger.debug(f"Cleaned up {len(keys_to_delete)} expired cache entries")
