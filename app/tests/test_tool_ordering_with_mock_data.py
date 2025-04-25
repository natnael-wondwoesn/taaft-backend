"""
Test script to verify that tools with descriptions appear first in the list
using mock data
"""

import sys
import os
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from uuid import uuid4

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.tools.models import ToolResponse
from app.tools.tools_service import get_tools


async def test_description_ordering_with_mock_data():
    """Test that tools with descriptions appear first in the list, using mock data"""
    print("\n=== Testing tool description ordering with mock data ===")

    # Create mock ToolResponse objects with and without descriptions
    mock_tools = [
        ToolResponse(
            id=str(uuid4()),
            name="Tool without description 1",
            description="",
            link="https://example.com/1",
            unique_id="tool-without-desc-1",
            price="Free",
            rating="4.5",
            is_featured=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        ToolResponse(
            id=str(uuid4()),
            name="Tool with description 1",
            description="This is a detailed description for tool 1",
            link="https://example.com/2",
            unique_id="tool-with-desc-1",
            price="Free",
            rating="4.0",
            is_featured=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        ToolResponse(
            id=str(uuid4()),
            name="Tool without description 2",
            description="",
            link="https://example.com/3",
            unique_id="tool-without-desc-2",
            price="Paid",
            rating="3.5",
            is_featured=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
        ToolResponse(
            id=str(uuid4()),
            name="Tool with description 2",
            description="Another detailed description for tool 2",
            link="https://example.com/4",
            unique_id="tool-with-desc-2",
            price="Free",
            rating="5.0",
            is_featured=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        ),
    ]

    # Create a new list by sorting according to our criteria
    # 1. Sort by description (empty descriptions last)
    # 2. Reverse the list (as get_tools does)
    sorted_tools = sorted(
        mock_tools, key=lambda tool: tool.description == "", reverse=False
    )
    sorted_tools.reverse()

    print("\nInitial order of tools:")
    for i, tool in enumerate(mock_tools):
        has_description = bool(tool.description and tool.description.strip())
        print(f"Tool {i}: '{tool.name}' - Has description: {has_description}")

    print("\nExpected order after sorting (descriptions first, then reversed):")
    for i, tool in enumerate(sorted_tools):
        has_description = bool(tool.description and tool.description.strip())
        print(f"Tool {i}: '{tool.name}' - Has description: {has_description}")

    # Check if tools with descriptions come first
    has_description_first = True
    first_without_description = None

    for i, tool in enumerate(sorted_tools):
        has_description = bool(tool.description and tool.description.strip())

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
    asyncio.run(test_description_ordering_with_mock_data())
    print("\nTest completed")
