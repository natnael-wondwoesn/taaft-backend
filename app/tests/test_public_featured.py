"""
Test script to verify public access to featured tools endpoint
"""

import sys
import os
import asyncio
import requests
from datetime import datetime
from uuid import uuid4
from urllib.parse import urljoin

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database.database import database

# Base URL for API
API_BASE_URL = "http://localhost:8000"


async def setup_test_data():
    """Create a featured test tool"""
    # Clear existing test tools first
    await database.tools.delete_many({"name": {"$regex": "^PublicFeatured"}})

    # Create a test tool
    test_tool = {
        "id": str(uuid4()),
        "name": "PublicFeatured Test Tool",
        "description": "Test tool for public featured endpoint",
        "link": "https://example.com/test",
        "unique_id": f"public-featured-{uuid4()}",
        "price": "Free",
        "category": "Testing",
        "is_featured": True,  # Mark as featured
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # Insert the test tool
    await database.tools.insert_one(test_tool)
    print(f"Created featured test tool with ID: {test_tool['id']}")

    return test_tool


async def cleanup_test_data():
    """Remove test data"""
    result = await database.tools.delete_many({"name": {"$regex": "^PublicFeatured"}})
    print(f"Removed {result.deleted_count} test tools")


def test_public_featured_endpoint():
    """Test public access to featured tools endpoint"""
    print("\n=== Testing public access to /tools/featured endpoint ===")

    # Try accessing the endpoint without authentication
    featured_url = urljoin(API_BASE_URL, "/tools/featured")

    # Make request without auth headers
    response = requests.get(featured_url)

    # Check if request was successful
    if response.status_code == 200:
        print("✓ Successfully accessed /tools/featured without authentication")
        data = response.json()
        featured_count = data.get("total", 0)
        tools = data.get("tools", [])
        print(f"Found {featured_count} featured tools")

        # Print first tool name if available
        if tools:
            print(f"First tool name: {tools[0].get('name', 'Unknown')}")

        return True
    else:
        print(
            f"✗ Failed to access /tools/featured: {response.status_code} - {response.text}"
        )
        return False


def test_sort_order():
    """Test sort order parameter on featured endpoint"""
    print("\n=== Testing sort_order parameter on /tools/featured endpoint ===")

    # Test descending order
    featured_url = urljoin(API_BASE_URL, "/tools/featured?sort_by=name&sort_order=desc")

    response = requests.get(featured_url)

    if response.status_code == 200:
        print("✓ Successfully accessed /tools/featured with sort_order=desc")
        data = response.json()
        tools = data.get("tools", [])

        if len(tools) > 1:
            # Check if the names are in descending order
            names = [tool.get("name", "") for tool in tools]
            print(f"Tool names in descending order: {names}")

            # Check if the names are sorted correctly
            sorted_names = sorted(names, reverse=True)
            if names == sorted_names:
                print("✓ Tools are correctly sorted in descending order")
            else:
                print("✗ Tools are not properly sorted in descending order")

        return True
    else:
        print(
            f"✗ Failed to access /tools/featured with sort_order=desc: {response.status_code} - {response.text}"
        )
        return False


async def run_tests():
    """Run all tests"""
    print("=== Testing Public Featured Tools Functionality ===")

    # Setup test data
    await setup_test_data()

    try:
        # Test public access
        test_public_featured_endpoint()

        # Test sort order
        test_sort_order()

    finally:
        # Clean up test data
        await cleanup_test_data()

    print("\nTests completed")


if __name__ == "__main__":
    asyncio.run(run_tests())
