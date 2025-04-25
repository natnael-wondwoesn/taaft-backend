"""
Test script to verify that tools with descriptions appear first in the list returned by get_tools
"""

import sys
import os
import asyncio
from typing import Dict, List, Any

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.tools.tools_service import get_tools
from app.models.user import UserResponse


async def test_tools_description_ordering():
    """Test that tools with descriptions appear first in the list"""
    print("\n=== Testing tool description ordering ===")

    # Create mock filters for featured tools (to reduce the result set)
    filters = {"is_featured": True}

    # Get tools
    tools = await get_tools(filters=filters)

    if not tools:
        print("No tools found to test ordering. Test inconclusive.")
        return

    print(f"Retrieved {len(tools)} tools")

    # Check if tools are ordered with descriptions first
    has_description_first = True

    # Track the position of the first tool without a description
    first_without_description = None

    for i, tool in enumerate(tools):
        has_description = bool(tool.description and tool.description.strip())

        print(f"Tool {i}: '{tool.name}' - Has description: {has_description}")

        # If this is the first tool without a description, mark its position
        if not has_description and first_without_description is None:
            first_without_description = i

        # If we've found a tool with a description after a tool without a description,
        # then the ordering is incorrect
        if has_description and first_without_description is not None:
            has_description_first = False
            print(
                f"❌ Tool with description found at position {i} after tool without description at position {first_without_description}"
            )

    # Verify the ordering is correct
    if has_description_first:
        print("✓ All tools with descriptions appear before tools without descriptions")
    else:
        print(
            "❌ Tools with descriptions do not all appear before tools without descriptions"
        )

    # Final assertion
    assert (
        has_description_first
    ), "Tools with descriptions should appear before tools without descriptions"

    return True


if __name__ == "__main__":
    # Run the test
    asyncio.run(test_tools_description_ordering())
    print("\nTest completed")
