"""
Test script to verify toggling featured status by unique_id
"""

import sys
import os
import asyncio
from datetime import datetime
from uuid import uuid4

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.database.database import database
from app.tools.tools_service import toggle_tool_featured_status_by_unique_id


async def setup_test_data():
    """Create a test tool for toggling featured status"""
    # Create a unique identifier for our test tool
    unique_id = f"test-unique-{uuid4()}"

    # Create test tool
    test_tool = {
        "id": str(uuid4()),
        "name": "Featured Test Tool",
        "description": "Test tool for toggling featured status by unique_id",
        "link": "https://example.com/test",
        "unique_id": unique_id,
        "price": "Free",
        "category": "Testing",
        "is_featured": False,  # Start as not featured
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    # Insert the test tool
    await database.tools.insert_one(test_tool)
    print(f"Created test tool with unique_id: {unique_id}")

    return unique_id


async def test_featured_status_toggle():
    """Test toggling featured status by unique_id"""
    # Create test data
    unique_id = await setup_test_data()

    # Verify initial state (not featured)
    tool = await database.tools.find_one({"unique_id": unique_id})
    if not tool:
        print("✗ Test failed - could not find created tool")
        return False

    print(f"Initial featured status: {tool.get('is_featured', False)}")

    # Toggle to featured
    print("\nSetting tool as featured...")
    updated_tool = await toggle_tool_featured_status_by_unique_id(unique_id, True)

    if not updated_tool:
        print("✗ Failed to update tool")
        return False

    print(f"Updated featured status: {updated_tool.is_featured}")

    # Verify update in database
    db_tool = await database.tools.find_one({"unique_id": unique_id})
    if db_tool and db_tool.get("is_featured") == True:
        print("✓ Database updated correctly to featured=True")
    else:
        print("✗ Database update failed")
        return False

    # Toggle back to not featured
    print("\nSetting tool as not featured...")
    updated_tool = await toggle_tool_featured_status_by_unique_id(unique_id, False)

    if not updated_tool:
        print("✗ Failed to update tool")
        return False

    print(f"Updated featured status: {updated_tool.is_featured}")

    # Verify update in database
    db_tool = await database.tools.find_one({"unique_id": unique_id})
    if db_tool and db_tool.get("is_featured") == False:
        print("✓ Database updated correctly to featured=False")
    else:
        print("✗ Database update failed")
        return False

    # Clean up
    result = await database.tools.delete_one({"unique_id": unique_id})
    print(f"\nTest cleanup complete. Removed {result.deleted_count} test tool")

    return True


async def main():
    """Run the tests"""
    print("=== Testing Featured Status Toggle by unique_id ===")
    success = await test_featured_status_toggle()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
