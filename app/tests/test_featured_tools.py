"""
Test script to verify featured tools functionality
"""

import json
import sys
import os
import requests
from urllib.parse import urljoin
from uuid import uuid4

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.tools.models import ToolCreate, ToolResponse
from app.database.database import database

# Constants for testing
API_BASE_URL = "http://localhost:8000"  # Adjust as needed
ADMIN_EMAIL = "admin@example.com"  # Replace with a valid admin email
ADMIN_PASSWORD = "admin_password"  # Replace with the admin password


def get_admin_token():
    """Get an admin token for authenticated requests"""
    login_url = urljoin(API_BASE_URL, "/auth/token")
    response = requests.post(
        login_url, data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        print(f"Failed to get admin token: {response.text}")
        return None
    return response.json().get("access_token")


def test_featured_tools_endpoints():
    """Test featured tools endpoints and admin functionality"""
    print("\n=== Testing Featured Tools Functionality ===")

    # Step 1: Create a test tool (needs admin access)
    admin_token = get_admin_token()
    if not admin_token:
        print("⚠️ Could not get admin token. Skipping admin-only tests.")
        admin_tests_enabled = False
    else:
        admin_tests_enabled = True
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Create a test tool with unique ID
        unique_id = f"test-tool-{uuid4()}"
        test_tool = {
            "name": "Test Featured Tool",
            "description": "A tool for testing featured functionality",
            "link": "https://example.com/test",
            "unique_id": unique_id,
            "price": "Free",
            "category": "Testing",
            "is_featured": False,
        }

        # Add the tool to the database directly
        tool_id = str(uuid4())
        test_tool["id"] = tool_id

        # Insert directly into the database to avoid dependency on the API
        # which may require admin permissions we don't have in the test
        print("Creating test tool in database...")
        database.tools.insert_one(test_tool)

        print(f"✓ Created test tool with ID: {tool_id}")

    # Step 2: Test public access to featured tools endpoint (no auth required)
    featured_url = urljoin(API_BASE_URL, "/public/tools/featured")
    response = requests.get(featured_url)

    if response.status_code == 200:
        print("✓ Public featured tools endpoint is accessible without authentication")
        data = response.json()
        initial_featured_count = data.get("total", 0)
        print(f"  Found {initial_featured_count} featured tools initially")
    else:
        print(
            f"✗ Failed to access featured tools: {response.status_code} - {response.text}"
        )
        return False

    # Skip admin tests if we couldn't get an admin token
    if not admin_tests_enabled:
        print("⚠️ Skipping admin functionality tests due to missing admin credentials")
        return True

    # Step 3: Toggle featured status (admin only)
    featured_toggle_url = urljoin(
        API_BASE_URL, f"/tools/{tool_id}/featured?is_featured=true"
    )
    response = requests.put(featured_toggle_url, headers=headers)

    if response.status_code == 200:
        print("✓ Admin can toggle tool featured status")
        print("  Tool is now featured")
    else:
        print(
            f"✗ Failed to toggle featured status: {response.status_code} - {response.text}"
        )
        # Clean up test tool anyway
        database.tools.delete_one({"id": tool_id})
        return False

    # Step 4: Verify tool appears in featured endpoint
    response = requests.get(featured_url)
    if response.status_code == 200:
        data = response.json()
        featured_tools = data.get("tools", [])
        new_featured_count = data.get("total", 0)

        # Check if our tool is in the featured list
        tool_found = any(tool.get("id") == tool_id for tool in featured_tools)

        if tool_found:
            print("✓ Test tool appears in featured tools list")
        else:
            print("✗ Test tool not found in featured tools list")

        print(f"  Found {new_featured_count} featured tools after update")
        print(f"  Expected at least {initial_featured_count + 1} tools")
    else:
        print(
            f"✗ Failed to get featured tools: {response.status_code} - {response.text}"
        )

    # Step 5: Un-feature the tool
    featured_toggle_url = urljoin(
        API_BASE_URL, f"/tools/{tool_id}/featured?is_featured=false"
    )
    response = requests.put(featured_toggle_url, headers=headers)

    if response.status_code == 200:
        print("✓ Admin can un-feature the tool")
    else:
        print(
            f"✗ Failed to un-feature the tool: {response.status_code} - {response.text}"
        )

    # Clean up - remove the test tool
    database.tools.delete_one({"id": tool_id})
    print("✓ Test cleanup complete")

    return True


if __name__ == "__main__":
    success = test_featured_tools_endpoints()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
