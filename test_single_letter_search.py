#!/usr/bin/env python3
"""
Test script to verify that single letter searches work correctly.
"""

import asyncio
import os
import sys
import logging

# Add the app directory to the Python path
sys.path.insert(0, "/home/ec2-user/taaft-backend")

from app.tools.tools_service import search_tools

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_single_letter_searches():
    """Test single letter searches."""
    logger.info("Testing single letter searches...")
    
    test_queries = ["a", "i", "o", "ai", "io", "app", "tool"]
    
    for query in test_queries:
        try:
            logger.info(f"\n=== Testing query: '{query}' ===")
            
            # Test search with limit
            result = await search_tools(
                search_term=query,
                limit=5,
                skip=0
            )
            
            if isinstance(result, dict):
                tools = result.get("tools", [])
                total = result.get("total", 0)
                
                logger.info(f"Query '{query}': Found {len(tools)} tools (total: {total})")
                
                if tools:
                    logger.info("Sample results:")
                    for i, tool in enumerate(tools[:3], 1):
                        logger.info(f"  {i}. {tool.name}")
                else:
                    logger.warning(f"No results found for '{query}'")
            else:
                logger.error(f"Unexpected result type for '{query}': {type(result)}")
                
        except Exception as e:
            logger.error(f"Error testing query '{query}': {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")


async def test_specific_single_letter():
    """Test the specific query 'a' that was reported as problematic."""
    logger.info("\n=== Testing specific query 'a' ===")
    
    try:
        result = await search_tools(
            search_term="a",
            limit=12,
            skip=0,
            sort_by="created_at",
            sort_order="desc"
        )
        
        if isinstance(result, dict):
            tools = result.get("tools", [])
            total = result.get("total", 0)
            
            logger.info(f"Query 'a': Found {len(tools)} tools (total: {total})")
            
            if tools:
                logger.info("Results:")
                for i, tool in enumerate(tools, 1):
                    logger.info(f"  {i}. {tool.name} - {tool.description[:100]}...")
                
                logger.info("✅ Single letter search 'a' is working!")
            else:
                logger.warning("❌ Query 'a' still returns no results")
        else:
            logger.error(f"Unexpected result type: {type(result)}")
            
    except Exception as e:
        logger.error(f"Error testing query 'a': {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


async def main():
    """Main test function."""
    logger.info("Starting single letter search tests...")
    
    # Test various single letter and short queries
    await test_single_letter_searches()
    
    # Test the specific problematic query
    await test_specific_single_letter()
    
    logger.info("Tests completed!")


if __name__ == "__main__":
    asyncio.run(main()) 