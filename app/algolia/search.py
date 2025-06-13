# # app/algolia/search.py
# """
# Enhanced search service for Algolia integration
# Handles natural language query processing for AI tool search
# """


"""
Enhanced search service for Algolia integration
Handles natural language query processing for AI tool search
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import datetime
import json
import openai
import os
from pydantic import ValidationError
import re

from .config import algolia_config
from .models import (
    SearchParams,
    SearchResult,
    SearchFacets,
    SearchFacet,
    NaturalLanguageQuery,
    ProcessedQuery,
    PricingType,
    AlgoliaToolRecord,
    JobImpactSearchResult,
    AlgoliaJobImpactRecord,
    JobImpactToolsSearchResult,
    JobImpactWithTools,
    TaskToolsSearchResult,
    JobToolsRecommendation,
    TaskWithTools,
)
from ..logger import logger


class AlgoliaSearch:
    """Service for NLP-based searching with Algolia"""

    def __init__(self):
        """Initialize the search service with Algolia config"""
        self.config = algolia_config
        # Initialize OpenAI for natural language processing
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key

        # Cache of known categories and pricing types
        self.known_categories = {}
        self.keyword_synonyms = {
            "writing": ["content creation", "text generation", "copywriting"],
            "image": ["image generation", "design", "graphic", "visual"],
            "audio": ["sound", "voice", "speech", "music"],
            "video": ["video generation", "animation"],
            "code": ["programming", "development", "coding", "software"],
            "marketing": ["seo", "social media", "advertising"],
            "data": ["analytics", "analysis", "visualization", "statistics"],
            "productivity": ["automation", "workflow", "efficiency"],
            "research": ["academic", "scientific", "study"],
            "chat": ["conversation", "assistant", "chatbot"],
            "e-commerce": ["shopping", "store", "retail", "sales"],
            "analytics": ["data analysis", "metrics", "performance", "tracking"],
        }

        # Price type mapping to standardize variations
        self.price_type_mapping = {
            "free": PricingType.FREE,
            "freemium": PricingType.FREEMIUM,
            "paid": PricingType.PAID,
            "premium": PricingType.PAID,
            "enterprise": PricingType.ENTERPRISE,
            "contact": PricingType.CONTACT,
            "contact for pricing": PricingType.CONTACT,
            "contact sales": PricingType.CONTACT,
        }

    async def perform_keyword_search(
        self,
        keywords: List[str],
        index_name: str = None,
        page: int = 0,
        per_page: int = 20,
    ) -> SearchResult:
        """
        Perform a search using keywords from chat conversation

        Args:
            keywords: List of keywords extracted from the conversation
            index_name: Optional index name to override the default tools index
            page: Page number (0-based for Algolia)
            per_page: Number of results per page

        Returns:
            Dictionary containing search results from Algolia
        """
        # Use the provided index name or fall back to the default tools index
        search_index = index_name or self.config.tools_index_name

        print(f"keywords: {keywords}")

        # Join keywords into a space-separated search query
        search_query = ", ".join(keywords) if keywords else ""

        logger.info(
            f"Performing keyword search: '{search_query}' on index '{search_index}'"
        )

        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return {
                "hits": [],
                "nbHits": 0,
                "page": page,
                "nbPages": 0,
                "processingTimeMS": 0,
            }

        try:
            # Construct the search request
            # print(f"{search_query}")
            # Convert the search query to the specified format with a placeholder popularity value
            # Using a fixed popularity value of 2.5658 as specified in the instructions
            # search_query = list(search_query.join())
            # Execute search using Algolia client
            search_params = {
                "query": search_query,
                "page": page,
                "hitsPerPage": per_page,
                "typoTolerance": "strict",  # Allow for typos in search
                "advancedSyntax": True,
                "removeWordsIfNoResults": "allOptional",  # Makes search more flexible
            }
            index_name = self.config.tools_index_name
            search_response = self.config.client.search_single_index(
                index_name=index_name, search_params=search_params
            )

            # Convert results to tool records
            tools = []
            for hit in search_response.hits:
                print(f"hit: {hit}")
                try:
                    # Create AlgoliaToolRecord from each hit
                    tool_record = AlgoliaToolRecord(
                        objectID=getattr(hit, "objectID", ""),
                        price=getattr(hit, "price", None),
                        name=getattr(hit, "name", None),
                        description=getattr(hit, "description", None),
                        link=getattr(hit, "link", None),
                        unique_id=getattr(hit, "unique_id", None),
                        rating=getattr(hit, "rating", None),
                        saved_numbers=getattr(hit, "saved_numbers", None),
                        category=getattr(hit, "category", None),
                        features=getattr(hit, "features", None),
                        is_featured=getattr(hit, "is_featured", False),
                        keywords=getattr(hit, "keywords", None),
                        categories=getattr(hit, "categories", None),
                        logo_url=getattr(hit, "logo_url", None),
                        user_reviews=getattr(hit, "user_reviews", None),
                        feature_list=getattr(hit, "feature_list", None),
                        referral_allow=getattr(hit, "referral_allow", False),
                        generated_description=getattr(
                            hit, "generated_description", None
                        ),
                        industry=getattr(hit, "industry", None),
                        created_at=getattr(hit, "created_at", None),
                        updated_at=getattr(hit, "updated_at", None),
                        carriers=getattr(hit, "carriers", None),
                    )
                    # print(f"tool_record: {tool_record}")
                    tools.append(tool_record)
                    print(f"tools: {tools}")
                except Exception as e:
                    logger.error(f"Error converting hit to AlgoliaToolRecord: {str(e)}")
                    continue
            print(f"tools: {tools}")
            # Create and return SearchResult
            return SearchResult(
                tools=tools,
                total=search_response.nb_hits,
                page=search_response.page,
                per_page=per_page,
                pages=search_response.nb_pages,
                processing_time_ms=search_response.processing_time_ms,
            )
        except Exception as e:
            logger.error(f"Error performing keyword search: {str(e)}")
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
            )

    def extract_keywords_from_chat(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Extract keywords from chat messages for search

        Args:
            messages: List of chat messages with 'role' and 'content' fields

        Returns:
            List of relevant keywords for search
        """
        # Common stopwords to filter out
        stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "then",
            "else",
            "when",
            "at",
            "from",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "of",
            "in",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "where",
            "why",
            "how",
            "all",
            "any",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "can",
            "will",
            "just",
            "should",
            "now",
            "tool",
            "tools",
            "ai",
            "intelligence",
            "artificial",
            "model",
            "models",
            "system",
        }

        # Extract only user messages as these contain the intent
        user_messages = [
            msg["content"] for msg in messages if msg.get("role") == "user"
        ]

        if not user_messages:
            return []

        # Focus on the last 3 messages, with more weight on the most recent
        recent_messages = user_messages[-3:]

        # Combine messages with more weight to more recent ones
        weights = [0.5, 0.75, 1.0]
        weighted_text = ""

        for i, msg in enumerate(recent_messages):
            if i < len(weights):
                # Repeat more recent messages to give them more weight
                repeats = int(weights[i] * 10)
                weighted_text += " " + " ".join([msg] * repeats)
            else:
                weighted_text += " " + msg

        # Extract words, normalize
        words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", weighted_text.lower())

        # Remove stopwords and duplicates while preserving order
        filtered_words = []
        seen = set()

        for word in words:
            if word not in stopwords and word not in seen:
                filtered_words.append(word)
                seen.add(word)

        # Check for synonyms and add them
        extended_keywords = []
        for word in filtered_words:
            extended_keywords.append(word)
            # Check for synonyms
            for key, synonyms in self.keyword_synonyms.items():
                if word == key or word in synonyms:
                    # Add both the key and other synonyms
                    extended_keywords.append(key)
                    extended_keywords.extend([s for s in synonyms if s != word])

        # Remove duplicates from extended list while preserving order
        final_keywords = []
        seen = set()
        for word in extended_keywords:
            if word not in seen:
                final_keywords.append(word)
                seen.add(word)

        # Return top keywords (limit to reasonable number)
        return final_keywords[:15]

    async def search_from_chat(
        self,
        messages: List[Dict[str, Any]],
        index_name: str = None,
        page: int = 0,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """
        Search for tools based on chat conversation

        Args:
            messages: List of chat messages with 'role' and 'content' fields
            index_name: Optional index name to override the default
            page: Page number (0-based for Algolia)
            per_page: Number of results per page

        Returns:
            Dictionary containing search results from Algolia
        """
        # Extract keywords from chat messages
        keywords = self.extract_keywords_from_chat(messages)

        if not keywords:
            logger.warning("No keywords extracted from chat messages")
            return {
                "hits": [],
                "nbHits": 0,
                "page": page,
                "nbPages": 0,
                "processingTimeMS": 0,
                "keywords": [],
            }

        logger.info(f"Extracted keywords from chat: {keywords}")

        # Perform search using the extracted keywords
        results = await self.perform_keyword_search(
            keywords=keywords, index_name=index_name, page=page, per_page=per_page
        )

        # Add the keywords used to the results
        results["keywords"] = keywords

        return results

    def extract_keywords_from_text(self, text: str) -> List[str]:
        """
        Extract keywords from a single text string

        Args:
            text: The text to extract keywords from

        Returns:
            List of relevant keywords for search
        """
        if not text:
            return []

        # Create a fake message to use the existing extraction logic
        fake_messages = [{"role": "user", "content": text}]
        return self.extract_keywords_from_chat(fake_messages)

    async def get_known_keywords_from_database(self) -> List[str]:
        """
        Fetch all keywords from the database keywords collection.

        Returns:
            List of all keywords stored in the database
        """
        from ..database.database import keywords

        # Fetch all keywords from the database
        cursor = keywords.find({})

        # Process results
        keywords_list = []
        async for keyword_doc in cursor:
            # Check the field name - could be either 'keyword' or 'word' depending on
            # which function created it. The update_tool_keywords uses 'keyword',
            # while the get_tools function uses 'word'
            keyword_value = keyword_doc.get("keyword") or keyword_doc.get("word")

            if keyword_value and keyword_value not in keywords_list:
                keywords_list.append(keyword_value)

        return keywords_list

    async def direct_search_tools(
        self,
        query: str,
        page: int = 0,
        per_page: int = 20,
    ) -> SearchResult:
        """
        Search for tools directly by name or description using Algolia.
        This search is more flexible and doesn't require exact matches.

        Args:
            query: The search query text
            page: Page number (0-based for Algolia)
            per_page: Number of results per page

        Returns:
            SearchResult object containing the search results
        """
        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
            )

        try:
            # Set up search parameters to focus on name and description fields
            search_params = {
                "query": query,
                "restrictSearchableAttributes": ["name", "description"],
                "page": page,
                "hitsPerPage": per_page,
                "typoTolerance": "strict",  # Allow for typos in search
                "advancedSyntax": True,
                "removeWordsIfNoResults": "allOptional",  # Makes search more flexible
            }

            # Execute search using Algolia client
            index_name = self.config.tools_index_name
            search_response = self.config.client.search_single_index(
                index_name=index_name, search_params=search_params
            )

            # Convert results to tool records
            tools = []
            for hit in search_response.hits:
                # print(f"hit: {hit}")
                try:
                    # Create AlgoliaToolRecord from each hit
                    tool_record = AlgoliaToolRecord(
                        objectID=getattr(hit, "objectID", ""),
                        price=getattr(hit, "price", None),
                        name=getattr(hit, "name", None),
                        description=getattr(hit, "description", None),
                        link=getattr(hit, "link", None),
                        unique_id=getattr(hit, "unique_id", None),
                        rating=getattr(hit, "rating", None),
                        saved_numbers=getattr(hit, "saved_numbers", None),
                        category=getattr(hit, "category", None),
                        features=getattr(hit, "features", None),
                        is_featured=getattr(hit, "is_featured", False),
                        keywords=getattr(hit, "keywords", None),
                        categories=getattr(hit, "categories", None),
                        logo_url=getattr(hit, "logo_url", None),
                        user_reviews=getattr(hit, "user_reviews", None),
                        feature_list=getattr(hit, "feature_list", None),
                        referral_allow=getattr(hit, "referral_allow", False),
                        generated_description=getattr(
                            hit, "generated_description", None
                        ),
                        industry=getattr(hit, "industry", None),
                        created_at=getattr(hit, "created_at", None),
                        updated_at=getattr(hit, "updated_at", None),
                        carriers=getattr(hit, "carriers", None),
                    )
                    # print(f"tool_record: {tool_record}")
                    tools.append(tool_record)
                    print(f"tools: {tools}")
                except Exception as e:
                    logger.error(f"Error converting hit to AlgoliaToolRecord: {str(e)}")
                    continue
            print(f"tools: {tools}")
            # Create and return SearchResult
            return SearchResult(
                tools=tools,
                total=search_response.nb_hits,
                page=search_response.page,
                per_page=per_page,
                pages=search_response.nb_pages,
                processing_time_ms=search_response.processing_time_ms,
            )

        except Exception as e:
            logger.error(f"Error performing direct search: {str(e)}")
            # Return empty results on error
            return SearchResult(
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
            )

    async def direct_search_job_impacts(
        self,
        query: Optional[str] = None,
        job_title: Optional[str] = None,
        job_category: Optional[str] = None,
        industry: Optional[str] = None,
        min_impact_score: Optional[float] = None,
        task_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        page: int = 0,
        per_page: int = 20,
        sort_by: str = "impact_score",
    ) -> JobImpactSearchResult:
        """
        Search for job impacts directly using Algolia.
        
        This search allows filtering by job title, category, and other fields.

        Args:
            query: The search query text
            job_title: Filter by job title
            job_category: Filter by job category
            industry: Filter by industry
            min_impact_score: Minimum impact score (0-100)
            task_name: Filter by task name
            tool_name: Filter by tool name
            page: Page number (0-based for Algolia)
            per_page: Number of results per page
            sort_by: Sort order (impact_score, relevance, date)

        Returns:
            JobImpactSearchResult object containing the search results
        """
        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return JobImpactSearchResult(
                job_impacts=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
            )

        try:
            # Build filters
            filters = []
            if job_title:
                filters.append(f"job_title:{job_title}")
            if job_category:
                filters.append(f"job_category:{job_category}")
            if industry:
                filters.append(f"industry:{industry}")
            if min_impact_score is not None:
                filters.append(f"numeric_impact_score >= {min_impact_score}")
            if task_name:
                filters.append(f"task_names:{task_name}")
            if tool_name:
                filters.append(f"tool_names:{tool_name}")

            filter_str = " AND ".join(filters) if filters else ""

            # Determine sort order
            if sort_by == "impact_score":
                ranking = ["desc(numeric_impact_score)"]
            elif sort_by == "date":
                ranking = ["desc(created_at)"]
            else:  # relevance - use default Algolia ranking
                ranking = []

            # Set up search parameters
            search_params = {
                "query":query,
                "page": page,
                "hitsPerPage": per_page,
                # "filters": filter_str,
                "typoTolerance": "strict",  # Allow for typos in search
                "advancedSyntax": True,
                "removeWordsIfNoResults": "allOptional",  # Makes search more flexible
            }

            # if ranking:
            #     search_params["customRanking"] = ranking

            # Execute search using Algolia client
            index_name = self.config.tools_job_impacts_index_name
            search_response = self.config.client.search_single_index(
                index_name=index_name, 
                # query=query, 
                search_params=search_params
            )

            # Convert results to job impact records
            job_impacts = []
            for hit in search_response.hits:
                try:
                    # Create AlgoliaJobImpactRecord from each hit
                    job_impact_record = AlgoliaJobImpactRecord(
                        objectID=getattr(hit, "objectID", ""),
                        job_title=getattr(hit, "job_title", None),
                        job_category=getattr(hit, "job_category", None),
                        industry=getattr(hit, "industry", None),
                        description=getattr(hit, "description", None),
                        ai_impact_score=getattr(hit, "ai_impact_score", None),
                        numeric_impact_score=getattr(hit, "numeric_impact_score", None),
                        ai_impact_summary=getattr(hit, "ai_impact_summary", None),
                        detailed_analysis=getattr(hit, "detailed_analysis", None),
                        tasks=getattr(hit, "tasks", None),
                        task_names=getattr(hit, "task_names", None),
                        tool_names=getattr(hit, "tool_names", None),
                        keywords=getattr(hit, "keywords", None),
                        created_at=getattr(hit, "created_at", None),
                        updated_at=getattr(hit, "updated_at", None),
                        source_date=getattr(hit, "source_date", None),
                        detail_page_link=getattr(hit, "detail_page_link", None),
                    )
                    job_impacts.append(job_impact_record)
                except Exception as e:
                    logger.error(f"Error converting hit to AlgoliaJobImpactRecord: {str(e)}")
                    continue

            # Create and return JobImpactSearchResult
            return JobImpactSearchResult(
                job_impacts=job_impacts,
                total=search_response.nb_hits,
                page=search_response.page,
                per_page=per_page,
                pages=search_response.nb_pages,
                processing_time_ms=search_response.processing_time_ms,
            )

        except Exception as e:
            logger.error(f"Error performing job impact search: {str(e)}")
            # Return empty results on error
            return JobImpactSearchResult(
                job_impacts=[],
                total=0,
                page=page,
                per_page=per_page,
                pages=0,
                processing_time_ms=0,
            )

    async def search_job_impacts_with_tools(
        self,
        job_title: str,
        job_category: Optional[str] = None,
        industry: Optional[str] = None,
        min_impact_score: Optional[float] = None,
        page: int = 0,
        per_page: int = 10,
        sort_by: str = "impact_score",
    ) -> JobImpactToolsSearchResult:
        """
        Perform a multi-step search from job title to tasks to tools.
        
        This search flow:
        1. Searches job impacts by job title
        2. For each job impact, extracts task names
        3. For each task name, searches tools that are relevant to that task
        4. Returns job impacts with associated tools grouped by task
        
        Args:
            job_title: Job title to search for
            job_category: Optional filter for job category
            industry: Optional filter for industry
            min_impact_score: Minimum impact score (0-100)
            page: Page number (0-based for Algolia)
            per_page: Number of job impacts per page
            sort_by: Sort order (impact_score, relevance, date)
            
        Returns:
            JobImpactToolsSearchResult containing job impacts with tools grouped by task
        """
        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return JobImpactToolsSearchResult(
                results=[],
                total=0,
                page=page,
                per_page=per_page,
                job_title=job_title,
                processing_time_ms=0,
            )
            
        try:
            # Step 1: Search for job impacts related to the job title
            job_impacts_result = await self.direct_search_job_impacts(
                query=None,  # We'll use job_title as a filter instead
                job_title=job_title,
                job_category=job_category,
                industry=industry,
                min_impact_score=min_impact_score,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
            )
            
            # If no job impacts found, return empty result
            if not job_impacts_result.job_impacts:
                return JobImpactToolsSearchResult(
                    results=[],
                    total=0,
                    page=page,
                    per_page=per_page,
                    job_title=job_title,
                    processing_time_ms=job_impacts_result.processing_time_ms,
                )
                
            # Step 2 & 3: For each job impact, find tools for each task
            results = []
            start_time = datetime.datetime.now()
            
            for job_impact in job_impacts_result.job_impacts:
                # Initialize the job impact with tools result
                job_impact_with_tools = JobImpactWithTools(
                    job_impact=job_impact,
                    tools_by_task={}
                )
                
                # Extract unique task names from the job impact
                task_names = job_impact.task_names or []
                
                # For each task, search for relevant tools
                for task_name in task_names:
                    # Skip empty task names
                    if not task_name:
                        continue
                        
                    # Search for tools related to this task
                    tools_result = await self.direct_search_tools(
                        query=task_name,
                        page=0,  # Always get first page for tasks
                        per_page=5,  # Limit to 5 tools per task to avoid overwhelming results
                    )
                    
                    # Add tools to the result if any were found
                    if tools_result.tools:
                        job_impact_with_tools.tools_by_task[task_name] = tools_result.tools
                
                # Add the job impact with its tools to the results
                results.append(job_impact_with_tools)
                
            # Calculate total processing time
            end_time = datetime.datetime.now()
            total_processing_time = (end_time - start_time).total_seconds() * 1000
                
            # Return the combined results
            return JobImpactToolsSearchResult(
                results=results,
                total=job_impacts_result.total,
                page=job_impacts_result.page,
                per_page=job_impacts_result.per_page,
                job_title=job_title,
                processing_time_ms=int(total_processing_time + job_impacts_result.processing_time_ms),
            )
            
        except Exception as e:
            logger.error(f"Error performing job impacts with tools search: {str(e)}")
            # Return empty results on error
            return JobImpactToolsSearchResult(
                results=[],
                total=0,
                page=page,
                per_page=per_page,
                job_title=job_title,
                processing_time_ms=0,
            )

    async def search_tools_by_task(
        self,
        task_name: str,
        page: int = 0,
        per_page: int = 10,
    ) -> Tuple[TaskToolsSearchResult, bool]:
        """
        Search for tools relevant to a specific task name.
        
        Args:
            task_name: Name of the task to find tools for
            page: Page number (0-based for Algolia)
            per_page: Number of tools per page
            
        Returns:
            Tuple of (TaskToolsSearchResult, from_cache) indicating the search result and
            whether it came from cache
        """
        from ..services.redis_cache import redis_client, REDIS_CACHE_ENABLED
        
        # Try to get from cache first if Redis is enabled
        from_cache = False
        if REDIS_CACHE_ENABLED and redis_client:
            try:
                cache_key = f"task_tools:{task_name}:{page}:{per_page}"
                cached_result = await redis_client.get(cache_key)
                if cached_result:
                    import json
                    from .models import AlgoliaToolRecord, TaskToolsSearchResult
                    
                    # Deserialize the cached result
                    result_dict = json.loads(cached_result)
                    
                    # Reconstruct the tool records
                    tools = []
                    for tool_dict in result_dict.get("tools", []):
                        tools.append(AlgoliaToolRecord(**tool_dict))
                    
                    # Reconstruct and return the TaskToolsSearchResult
                    result = TaskToolsSearchResult(
                        task_name=result_dict.get("task_name"),
                        tools=tools,
                        total=result_dict.get("total"),
                        page=result_dict.get("page"),
                        per_page=result_dict.get("per_page"),
                        processing_time_ms=result_dict.get("processing_time_ms"),
                    )
                    from_cache = True
                    return result, from_cache
            except Exception as e:
                logger.error(f"Error retrieving cached task tools: {str(e)}")
                # Continue with the normal search flow if cache retrieval fails
        
        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty search results.")
            return TaskToolsSearchResult(
                task_name=task_name,
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                processing_time_ms=0,
            ), from_cache
            
        try:
            # Search for tools related to this task
            start_time = datetime.datetime.now()
            
            tools_result = await self.direct_search_tools(
                query=task_name,
                page=page,
                per_page=per_page,
            )
            
            # Calculate processing time
            end_time = datetime.datetime.now()
            processing_time_ms = int((end_time - start_time).total_seconds() * 1000) + tools_result.processing_time_ms
            
            # Create the result
            result = TaskToolsSearchResult(
                task_name=task_name,
                tools=tools_result.tools,
                total=tools_result.total,
                page=tools_result.page,
                per_page=tools_result.per_page,
                processing_time_ms=processing_time_ms,
            )
            
            # Cache the result if Redis is enabled
            if REDIS_CACHE_ENABLED and redis_client:
                try:
                    cache_key = f"task_tools:{task_name}:{page}:{per_page}"
                    # Serialize the result
                    import json
                    
                    # Convert the tools to dictionaries
                    tools_dict = []
                    for tool in result.tools:
                        tools_dict.append(tool.model_dump())
                    
                    # Create a dictionary representation of the result
                    result_dict = {
                        "task_name": result.task_name,
                        "tools": tools_dict,
                        "total": result.total,
                        "page": result.page,
                        "per_page": result.per_page,
                        "processing_time_ms": result.processing_time_ms,
                    }
                    
                    # Cache for 1 hour (3600 seconds)
                    await redis_client.setex(
                        cache_key, 
                        3600, 
                        json.dumps(result_dict, default=str)
                    )
                except Exception as e:
                    logger.error(f"Error caching task tools: {str(e)}")
                    # Continue even if caching fails
            
            return result, from_cache
            
        except Exception as e:
            logger.error(f"Error searching tools by task: {str(e)}")
            # Return empty results on error
            return TaskToolsSearchResult(
                task_name=task_name,
                tools=[],
                total=0,
                page=page,
                per_page=per_page,
                processing_time_ms=0,
            ), from_cache

    async def get_job_tools_recommendation(
        self,
        job_title: str,
        max_tasks: int = 5,
        max_tools_per_task: int = 3,
    ) -> JobToolsRecommendation:
        """
        Get a simplified job-to-tools recommendation.
        
        This method provides a streamlined workflow that:
        1. Finds the most relevant job impact for the job title
        2. Extracts the most important tasks
        3. Finds the most relevant tools for each task
        4. Returns a flat structure with tasks and their tools
        
        Args:
            job_title: Job title to search for
            max_tasks: Maximum number of tasks to include
            max_tools_per_task: Maximum number of tools per task
            
        Returns:
            JobToolsRecommendation with tasks and their recommended tools
        """
        # Check if Algolia is configured
        if not self.config.is_configured():
            logger.warning("Algolia not configured. Returning empty recommendation.")
            return JobToolsRecommendation(
                job_title=job_title,
                tasks_with_tools=[],
                task_count=0,
                total_tool_count=0,
                processing_time_ms=0,
            )
            
        try:
            start_time = datetime.datetime.now()
            
            # Step 1: Get the most relevant job impact for this job title
            job_impacts_result = await self.direct_search_job_impacts(
                query=None,
                job_title=job_title,
                page=0,
                per_page=1,  # Just get the most relevant one
                sort_by="impact_score",
            )
            
            # If no job impacts found, return empty result
            if not job_impacts_result.job_impacts:
                end_time = datetime.datetime.now()
                processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
                
                return JobToolsRecommendation(
                    job_title=job_title,
                    tasks_with_tools=[],
                    task_count=0,
                    total_tool_count=0,
                    processing_time_ms=processing_time_ms,
                )
                
            # Get the best matching job impact
            job_impact = job_impacts_result.job_impacts[0]
            
            # Initialize the recommendation object
            recommendation = JobToolsRecommendation(
                job_title=job_title,
                job_category=job_impact.job_category,
                industry=job_impact.industry,
                ai_impact_score=job_impact.ai_impact_score,
                ai_impact_summary=job_impact.ai_impact_summary,
                tasks_with_tools=[],
                task_count=0,
                total_tool_count=0,
            )
            
            # Step 2: Extract task names and limit to max_tasks
            task_names = job_impact.task_names or []
            if len(task_names) > max_tasks:
                task_names = task_names[:max_tasks]
                
            # For tracking counts
            total_tools = 0
            tasks_with_tools_count = 0
                
            # Step 3: For each task, get tools
            for task_name in task_names:
                if not task_name:
                    continue
                    
                # Get tools for this task
                tools_result = await self.direct_search_tools(
                    query=task_name,
                    page=0,
                    per_page=max_tools_per_task,
                )
                
                # Only add tasks that have tools
                if tools_result.tools:
                    tool_count = len(tools_result.tools)
                    task_with_tools = TaskWithTools(
                        task_name=task_name,
                        tools=tools_result.tools,
                        tool_count=tool_count,
                    )
                    recommendation.tasks_with_tools.append(task_with_tools)
                    
                    # Update counters
                    tasks_with_tools_count += 1
                    total_tools += tool_count
            
            # Set the count fields
            recommendation.task_count = tasks_with_tools_count
            recommendation.total_tool_count = total_tools
            
            # Calculate processing time
            end_time = datetime.datetime.now()
            recommendation.processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error getting job tools recommendation: {str(e)}")
            # Return a basic result on error
            return JobToolsRecommendation(
                job_title=job_title,
                tasks_with_tools=[],
                task_count=0,
                total_tool_count=0,
                processing_time_ms=0,
            )


# Create a singleton instance of AlgoliaSearch
algolia_search = AlgoliaSearch()


async def format_search_results_summary(search_results: Dict[str, Any]) -> str:
    """
    Format the results from perform_keyword_search into a structured summary.

    Args:
        search_results: Dictionary or object containing search results from Algolia

    Returns:
        A formatted string with a summary of the search results
    """
    # Extract key information from search results - handle both dict and object formats
    if hasattr(search_results, "nb_hits"):
        num_hits = search_results.nb_hits
        hits = search_results.hits
    else:
        num_hits = search_results.get("nbHits", 0)
        hits = search_results.get("hits", [])

    print(f"hits: {hits}")
    # Create the initial greeting message
    summary = f"Hey! Great News! I have found Plenty of tools to help you from our directory.\n\n"

    # If no results were found, provide a message
    if num_hits == 0:
        summary += "Unfortunately, I couldn't find any matching tools. Try broadening your search terms."
        return summary

    # Add a structured list of the top tools found
    summary += "Here are the top tools I found for you:\n\n"

    # Process each hit/tool into a structured format
    for i, hit in enumerate(hits, 1):
        if i > 10:  # Limit to top 10 for readability
            break

        # Get properties with fallbacks for missing data - handle both dict and object formats
        if isinstance(hit, dict):
            name = hit.get("name", "Unnamed Tool")
            description = hit.get("description", "No description available.")
            pricing = hit.get("pricing_type", "")
            categories = hit.get("categories", [])
            url = hit.get("url", "")
        else:
            name = getattr(hit, "name", "Unnamed Tool")
            description = getattr(hit, "description", "No description available.")
            pricing = getattr(hit, "pricing_type", "")
            categories = getattr(hit, "categories", [])
            url = getattr(hit, "url", "")

        if pricing:
            pricing = pricing.capitalize()

        # Format each tool entry
        summary += f"📌 {name}\n"
        summary += f"   {description}\n"
        if pricing:
            summary += f"   💰 {pricing}\n"
        if categories and isinstance(categories, list):
            cat_text = ", ".join(categories)
            summary += f"   🏷️ {cat_text}\n"
        if url:
            summary += f"   🔗 {url}\n"
        summary += "\n"

    # Add a footer if there are more results than shown
    if num_hits > 10:
        remaining = num_hits - 10
        summary += (
            f"...and {remaining} more tool{'s' if remaining > 1 else ''} available."
        )

    return summary
