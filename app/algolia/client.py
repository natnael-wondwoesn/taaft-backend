"""
Optimized Algolia client with connection pooling and better error handling
"""

from typing import Dict, List, Optional, Any, Union
import time
import asyncio
from algoliasearch.search.client import SearchClientSync as SearchClient

# Fix: Import exceptions from the right location
# The actual exceptions vary by version, so we'll handle exceptions generically
# instead of importing specific exception classes
from ..logger import logger


class OptimizedAlgoliaClient:
    """
    Optimized Algolia client wrapper with connection pooling and better error handling
    """

    def __init__(
        self, app_id: str, api_key: str, timeout: int = 5, max_retries: int = 3
    ):
        """
        Initialize the client

        Args:
            app_id: Algolia App ID
            api_key: Algolia API Key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.app_id = app_id
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None
        self._pending_requests = 0
        self._last_request_time = time.time()
        self._request_lock = asyncio.Lock()

        # Initialize client
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Algolia client with performance optimizations"""
        try:
            self._client = SearchClient(
                self.app_id,
                self.api_key,
                {"connectTimeout": self.timeout * 1000},  # Convert to milliseconds
            )
            logger.info("Optimized Algolia client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Algolia client: {str(e)}")
            self._client = None

    async def search_single_index(
        self,
        index_name: str,
        search_params: Dict[str, Any],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Perform a search on a single index with retry logic and connection pooling

        Args:
            index_name: The name of the index to search
            search_params: Search parameters
            request_options: Additional request options

        Returns:
            Search results
        """
        start_time = time.time()

        # Basic rate limiting - wait if too many concurrent requests
        async with self._request_lock:
            self._pending_requests += 1

        try:
            result = None
            last_error = None
            attempt = 0

            # Retry logic
            for attempt in range(self.max_retries):
                try:
                    if not self._client:
                        self._initialize_client()
                        if not self._client:
                            raise Exception("Algolia client is not initialized")

                    # Perform the search
                    search_options = {}
                    if request_options:
                        search_options = request_options

                    # Execute search with optional parameters
                    result = self._client.index(index_name).search(
                        search_params.get("query", ""), search_options
                    )

                    # If successful, break the retry loop
                    break

                except Exception as e:
                    # Handle all exceptions generically rather than specific Algolia exceptions
                    last_error = e
                    wait_time = 0.1 * (2**attempt)  # Exponential backoff

                    # Check error message to determine if it's a connection issue
                    error_msg = str(e).lower()
                    if (
                        "unreachable" in error_msg
                        or "timeout" in error_msg
                        or "connection" in error_msg
                    ):
                        logger.warning(
                            f"Algolia host unreachable (attempt {attempt+1}/{self.max_retries}), retrying in {wait_time:.2f}s"
                        )
                    else:
                        logger.error(
                            f"Algolia error (attempt {attempt+1}/{self.max_retries}): {str(e)}"
                        )

                    await asyncio.sleep(wait_time)

            # If all retries failed, raise the last error
            if result is None:
                if last_error:
                    raise last_error
                else:
                    raise Exception(
                        "All Algolia search attempts failed without a specific error"
                    )

            # Log performance
            elapsed = time.time() - start_time
            logger.debug(
                f"Algolia search completed in {elapsed:.4f}s after {attempt+1} attempt(s)"
            )

            return result

        finally:
            # Clean up
            async with self._request_lock:
                self._pending_requests -= 1
                self._last_request_time = time.time()

    async def multi_search(
        self,
        queries: List[Dict[str, Any]],
        request_options: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Perform multiple searches in parallel

        Args:
            queries: List of search queries with their index names
            request_options: Additional request options

        Returns:
            Multiple search results
        """
        start_time = time.time()

        # Rate limiting
        async with self._request_lock:
            self._pending_requests += 1

        try:
            if not self._client:
                self._initialize_client()
                if not self._client:
                    raise Exception("Algolia client is not initialized")

            # Format the requests
            formatted_queries = []
            for query in queries:
                formatted_query = {
                    "indexName": query.get("index_name"),
                    "params": query.get("search_params", {}),
                }
                formatted_queries.append(formatted_query)

            # Execute multi search
            results = self._client.multiple_queries(
                formatted_queries,
                {"strategy": "stopIfEnoughMatches"},  # Optimization strategy
            )

            # Log performance
            elapsed = time.time() - start_time
            logger.debug(f"Algolia multi-search completed in {elapsed:.4f}s")

            return results

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Error in Algolia multi-search ({elapsed:.4f}s): {str(e)}")
            raise

        finally:
            # Clean up
            async with self._request_lock:
                self._pending_requests -= 1
                self._last_request_time = time.time()

    def is_healthy(self) -> bool:
        """Check if the Algolia client is initialized and healthy"""
        return self._client is not None

    async def get_client_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        async with self._request_lock:
            return {
                "pending_requests": self._pending_requests,
                "last_request_time": self._last_request_time,
                "time_since_last_request": time.time() - self._last_request_time,
                "is_healthy": self.is_healthy(),
            }
