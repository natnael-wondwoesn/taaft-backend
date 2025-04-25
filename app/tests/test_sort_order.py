"""
Test script to verify sort order functionality works correctly
"""

import sys
import os
import asyncio
from datetime import datetime
from uuid import uuid4

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database.database import database
from app.tools.tools_service import get_tools


async def setup_test_data():
    """Create some test tools for sorting tests"""
    # Clear existing test tools first
    await database.tools.delete_many({"name": {"$regex": "^SortTest"}})

    # Create 3 test tools with different names
    test_tools = [
        {
            "id": str(uuid4()),
            "name": "SortTest A",
            "description": "Test tool A for sorting",
            "link": "https://example.com/a",
            "unique_id": f"sorttest-a-{uuid4()}",
            "price": "Free",
            "category": "Testing",
            "is_featured": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid4()),
            "name": "SortTest B",
            "description": "Test tool B for sorting",
            "link": "https://example.com/b",
            "unique_id": f"sorttest-b-{uuid4()}",
            "price": "Paid",
            "category": "Testing",
            "is_featured": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "id": str(uuid4()),
            "name": "SortTest C",
            "description": "Test tool C for sorting",
            "link": "https://example.com/c",
            "unique_id": f"sorttest-c-{uuid4()}",
            "price": "Freemium",
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


async def test_sort_order():
    """Test sorting in ascending and descending order"""
    # Create test data
    test_tools = await setup_test_data()

    # Get tools with ascending sort by name
    print("\nTesting ASCENDING sort by name:")
    filters = {"name": {"$regex": "^SortTest"}}
    asc_tools = await get_tools(filters=filters, sort_by="name", sort_order="asc")

    # Print the order
    print("Ascending order:")
    for tool in asc_tools:
        print(f"  - {tool.name}")

    # Check if ascending order is correct
    tool_names = [tool.name for tool in asc_tools]
    expected_asc = ["SortTest A", "SortTest B", "SortTest C"]

    if tool_names == expected_asc:
        print("✓ Ascending order is correct")
    else:
        print(
            f"✗ Ascending order is incorrect. Expected: {expected_asc}, Got: {tool_names}"
        )

    # Get tools with descending sort by name
    print("\nTesting DESCENDING sort by name:")
    desc_tools = await get_tools(filters=filters, sort_by="name", sort_order="desc")

    # Print the order
    print("Descending order:")
    for tool in desc_tools:
        print(f"  - {tool.name}")

    # Check if descending order is correct
    tool_names = [tool.name for tool in desc_tools]
    expected_desc = ["SortTest C", "SortTest B", "SortTest A"]

    if tool_names == expected_desc:
        print("✓ Descending order is correct")
    else:
        print(
            f"✗ Descending order is incorrect. Expected: {expected_desc}, Got: {tool_names}"
        )

    # Clean up test data
    result = await database.tools.delete_many({"name": {"$regex": "^SortTest"}})
    print(f"\nRemoved {result.deleted_count} test tools")


async def main():
    """Run the tests"""
    print("=== Testing Tool Sorting Functionality ===")
    await test_sort_order()
    print("\nTests completed")


if __name__ == "__main__":
    asyncio.run(main())
