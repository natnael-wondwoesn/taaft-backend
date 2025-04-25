"""
Service to transform Algolia search results to desired format
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def format_tools_to_desired_format(search_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform the original formatted_data to the desired format.
    This will extract only the required fields and format them per the specification.

    Args:
        search_results: The original search results from Algolia

    Returns:
        A dictionary with the transformed data structure containing only the specified fields
    """
    if not search_results:
        return {"hits": [], "nbHits": 0}

    # Extract hits from different possible formats
    hits = []
    if isinstance(search_results, dict):
        # Standard dictionary format
        hits = search_results.get("hits", [])
    elif hasattr(search_results, "hits"):
        # Object with hits attribute
        hits = search_results.hits

    # If hits is empty or None, return empty result
    if not hits:
        return {"hits": [], "nbHits": 0}

    # Extract search query for tags if available
    search_tags = []
    if isinstance(search_results, dict):
        search_query = search_results.get("query", "")
    elif hasattr(search_results, "query"):
        search_query = search_results.query
    else:
        search_query = ""

    # Convert search query to tags if it exists
    if search_query:
        # Split by commas and spaces, remove empty tags
        search_tags = [
            tag.strip() for tag in search_query.replace(",", " ").split() if tag.strip()
        ]

    formatted_hits = []

    for hit in hits:
        try:
            # Get category_id safely, ensuring it's not None before calling replace
            category_id = safe_get(hit, "category_id", "")
            if category_id is not None:
                category_id = category_id.replace('"', "")
            else:
                category_id = ""

            # Use safe_get to handle both dict-like objects and objects with attributes
            formatted_hit = {
                "objectID": safe_get(hit, "objectID", ""),
                "name": safe_get(hit, "name", "Unknown Tool"),
                "description": safe_get(hit, "description", ""),
                "link": safe_get(hit, "link", ""),
                "logo_url": safe_get(hit, "logo_url", ""),
                "category_id": category_id,
                "unique_id": safe_get(hit, "unique_id", safe_get(hit, "object_id", "")),
                "price": safe_get(hit, "price", ""),
                "rating": safe_get(hit, "rating", "0.0"),
                "search_tags": search_tags,
            }

            # Ensure none of the values are None
            for key, value in formatted_hit.items():
                if value is None:
                    formatted_hit[key] = ""

            formatted_hits.append(formatted_hit)
        except Exception as e:
            logger.error(f"Error formatting hit: {str(e)}")
            # Create a minimal valid hit structure with empty values
            minimal_hit = {
                "objectID": safe_get(hit, "objectID", ""),
                "name": safe_get(hit, "name", "Unknown Tool"),
                "description": "",
                "link": safe_get(hit, "link", ""),
                "logo_url": "",
                "category_id": "",
                "unique_id": safe_get(hit, "unique_id", safe_get(hit, "object_id", "")),
                "price": "",
                "rating": "0.0",
                "search_tags": search_tags,
            }

            # Ensure none of the values are None
            for key, value in minimal_hit.items():
                if value is None:
                    minimal_hit[key] = ""

            formatted_hits.append(minimal_hit)

    # Get the correct count - if we have nbHits in the original data, use that
    nbHits = 0
    if isinstance(search_results, dict) and "nbHits" in search_results:
        nbHits = search_results["nbHits"]
    elif hasattr(search_results, "nbHits"):
        nbHits = search_results.nbHits
    else:
        nbHits = len(formatted_hits)

    # Create response structure with the correct hit count
    result = {"hits": formatted_hits, "nbHits": nbHits}

    # Final check to ensure no None values remain
    for hit in result["hits"]:
        for key, value in hit.items():
            if value is None:
                hit[key] = ""

    # Log information about the hits processed vs total hits
    logger.info(f"Formatted {len(formatted_hits)} hits out of {nbHits} total hits")

    return result


def safe_get(obj, attr, default=""):
    """
    Safely get an attribute from an object, whether it's a dictionary or an object with attributes.

    Args:
        obj: The object to get the attribute from
        attr: The attribute name to get
        default: The default value to return if the attribute doesn't exist

    Returns:
        The attribute value or the default
    """
    if obj is None:
        return default

    # Try dictionary access first
    if hasattr(obj, "get") and callable(obj.get):
        value = obj.get(attr, default)
        return value if value is not None else default

    # Try object attribute access
    if hasattr(obj, attr):
        value = getattr(obj, attr)
        return value if value is not None else default

    # Try dict-like access
    try:
        value = obj[attr]
        return value if value is not None else default
    except (KeyError, TypeError, IndexError):
        pass

    return default
