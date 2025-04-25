"""
Test script to verify sponsored tools endpoint
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
    """Create featured test tools"""
    # Clear existing test tools first
    await database.tools.delete_many({"name": {"$regex": "^Test(Featured|Sponsored)"}})

    # Create test tools
    test_tools = [
        {
            "id": str(uuid4()),
            "name": "TestFeatured Tool A",
            "description": "Test tool A for featured/sponsored endpoint",
            "link": "https://example.com/a",
            "unique_id": f"test-featured-a-{uuid4()}",
            "price": "Free",
            "category": "Testing",
            "is_featured": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid4()),
            "name": "TestSponsored Tool B",
            "description": "Test tool B for featured/sponsored endpoint",
            "link": "https://example.com/b",
            "unique_id": f"test-sponsored-b-{uuid4()}",
            "price": "Paid",
            "category": "Testing",
            "is_featured": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    ]

    # Insert the test tools
    await database.tools.insert_many(test_tools)
    print(f"Created {len(test_tools)} test tools")

    return test_tools


async def cleanup_test_data():
    """Remove test data"""
    result = await database.tools.delete_many(
        {"name": {"$regex": "^Test(Featured|Sponsored)"}}
    )
    print(f"Removed {result.deleted_count} test tools")


def test_featured_endpoint():
    """Test the featured tools endpoint"""
    print("\n=== Testing /tools/featured endpoint ===")

    featured_url = urljoin(API_BASE_URL, "/tools/featured")
    response = requests.get(featured_url)

    if response.status_code == 200:
        print("✓ Successfully accessed /tools/featured endpoint")
        data = response.json()
        tools = data.get("tools", [])
        total = data.get("total", 0)
        print(f"Found {total} featured tools")

        # Print tool names
        if tools:
            print("Featured tools:")
            for tool in tools:
                print(f"  - {tool.get('name', 'Unknown')}")

        return True
    else:
        print(
            f"✗ Failed to access /tools/featured: {response.status_code} - {response.text}"
        )
        return False


def test_sponsored_endpoint():
    """Test the sponsored tools endpoint"""
    print("\n=== Testing /tools/sponsored endpoint ===")

    sponsored_url = urljoin(API_BASE_URL, "/tools/sponsored")
    response = requests.get(sponsored_url)

    if response.status_code == 200:
        print("✓ Successfully accessed /tools/sponsored endpoint")
        data = response.json()
        tools = data.get("tools", [])
        total = data.get("total", 0)
        print(f"Found {total} sponsored tools")

        # Print tool names
        if tools:
            print("Sponsored tools:")
            for tool in tools:
                print(f"  - {tool.get('name', 'Unknown')}")

        # Since sponsored is identical to featured, they should have the same number of tools
        featured_response = requests.get(urljoin(API_BASE_URL, "/tools/featured"))
        featured_data = featured_response.json()
        featured_count = featured_data.get("total", 0)

        if total == featured_count:
            print("✓ Sponsored tools count matches featured tools count")
        else:
            print(f"✗ Count mismatch: Sponsored: {total}, Featured: {featured_count}")

        return True
    else:
        print(
            f"✗ Failed to access /tools/sponsored: {response.status_code} - {response.text}"
        )
        return False


def test_public_routes():
    """Test the public routes for featured and sponsored tools"""
    print("\n=== Testing public routes ===")

    endpoints = ["/public/tools/featured", "/public/tools/sponsored"]

    for endpoint in endpoints:
        url = urljoin(API_BASE_URL, endpoint)
        response = requests.get(url)

        if response.status_code == 200:
            print(f"✓ Successfully accessed {endpoint}")
            data = response.json()
            tools_count = len(data.get("tools", []))
            print(f"  Found {tools_count} tools")
        else:
            print(
                f"✗ Failed to access {endpoint}: {response.status_code} - {response.text}"
            )


def test_sort_order():
    """Test sort order on both endpoints"""
    print("\n=== Testing sort order ===")

    endpoints = ["/tools/featured", "/tools/sponsored"]

    for endpoint in endpoints:
        desc_url = urljoin(API_BASE_URL, f"{endpoint}?sort_by=name&sort_order=desc")
        response = requests.get(desc_url)

        if response.status_code == 200:
            print(f"✓ Successfully accessed {endpoint} with sort_order=desc")
            data = response.json()
            tools = data.get("tools", [])

            if len(tools) > 1:
                names = [tool.get("name", "") for tool in tools]
                print(f"  Tool names in descending order: {names}")

                # Check if names are in descending order
                sorted_names = sorted(names, reverse=True)
                if names == sorted_names:
                    print(f"  ✓ {endpoint} tools correctly sorted in descending order")
                else:
                    print(
                        f"  ✗ {endpoint} tools not properly sorted in descending order"
                    )
        else:
            print(
                f"✗ Failed to access {endpoint} with sort_order=desc: {response.status_code}"
            )


async def run_tests():
    """Run all tests"""
    print("=== Testing Sponsored Tools Functionality ===")

    # Setup test data
    await setup_test_data()

    try:
        # Test featured endpoint
        test_featured_endpoint()

        # Test sponsored endpoint
        test_sponsored_endpoint()

        # Test public routes
        test_public_routes()

        # Test sort order
        test_sort_order()

    finally:
        # Clean up test data
        await cleanup_test_data()

    print("\nTests completed")


if __name__ == "__main__":
    asyncio.run(run_tests())
