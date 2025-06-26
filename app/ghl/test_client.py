"""
Test client for interacting with the GoHighLevel API directly
Used for debugging and testing the integration with automatic token refresh
"""

import httpx
import json
import os
from typing import Dict, Any, Optional, List
import asyncio
from dotenv import load_dotenv
from .ghl_service import token_manager, GHLContactData

# Load environment variables
load_dotenv()

# GoHighLevel API Configuration
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "")
GHL_BASE_URL = "https://services.leadconnectorhq.com"


async def get_auth_headers():
    """Get authorization headers with fresh token."""
    try:
        access_token = await token_manager.get_valid_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Version": "2021-07-28",
            "Content-Type": "application/json",
        }
    except Exception as e:
        print(f"❌ Failed to get valid token: {str(e)}")
        return None


async def test_connection():
    """Test the connection to GoHighLevel API with automatic token refresh."""
    headers = await get_auth_headers()
    if not headers:
        print("⚠️ GHL tokens not configured or invalid")
        return False

    if not GHL_LOCATION_ID:
        print("⚠️ GHL_LOCATION_ID not configured")
        return False

    try:
        # Test endpoint that returns location info
        endpoint = f"{GHL_BASE_URL}/locations/{GHL_LOCATION_ID}"

        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers)

            if response.status_code == 200:
                location_data = response.json()
                print(f"✅ Successfully connected to GoHighLevel")
                print(
                    f"Location: {location_data.get('location', {}).get('name', 'N/A')}"
                )
                return True
            else:
                print(f"❌ Connection failed: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        print(f"❌ Error testing connection: {str(e)}")
        return False


async def get_contacts(limit: int = 10):
    """Get contacts from GoHighLevel with automatic token refresh."""
    headers = await get_auth_headers()
    if not headers:
        return None

    try:
        # Get contacts endpoint
        endpoint = f"{GHL_BASE_URL}/contacts/"
        params = {
            "locationId": GHL_LOCATION_ID,
            "limit": limit,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, headers=headers, params=params)

            if response.status_code == 200:
                contacts_data = response.json()
                print(f"✅ Retrieved {len(contacts_data.get('contacts', []))} contacts")

                # Print first contact details
                if contacts_data.get("contacts"):
                    first_contact = contacts_data["contacts"][0]
                    print("\nSample Contact:")
                    print(
                        f"Name: {first_contact.get('firstName', '')} {first_contact.get('lastName', '')}"
                    )
                    print(f"Email: {first_contact.get('email', 'N/A')}")
                    print(f"Tags: {', '.join(first_contact.get('tags', []))}")

                return contacts_data
            else:
                print(
                    f"❌ Failed to get contacts: {response.status_code} - {response.text}"
                )
                return None

    except Exception as e:
        print(f"❌ Error getting contacts: {str(e)}")
        return None


async def create_test_contact(email: str, first_name: str, last_name: str):
    """Create a test contact in GoHighLevel with automatic token refresh."""
    headers = await get_auth_headers()
    if not headers:
        return None

    try:
        # Create contact endpoint
        endpoint = f"{GHL_BASE_URL}/contacts"

        payload = {
            "locationId": GHL_LOCATION_ID,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "source": "TAAFT Test",
            "tags": ["TAAFT Test Contact"],
            "customFields": {"test_field": "This is a test contact"},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code in (200, 201):
                contact_data = response.json()
                print(f"✅ Successfully created test contact: {email}")
                print(f"Contact ID: {contact_data.get('id', 'N/A')}")
                return contact_data
            else:
                print(
                    f"❌ Failed to create contact: {response.status_code} - {response.text}"
                )
                return None

    except Exception as e:
        print(f"❌ Error creating contact: {str(e)}")
        return None


async def add_tag_to_contact(contact_id: str, tag: str):
    """Add a tag to a contact in GoHighLevel with automatic token refresh."""
    headers = await get_auth_headers()
    if not headers:
        return False

    try:
        # First get current contact to get existing tags
        endpoint = f"{GHL_BASE_URL}/contacts/{contact_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoint, headers=headers, params={"locationId": GHL_LOCATION_ID}
            )

            if response.status_code != 200:
                print(
                    f"❌ Failed to get contact: {response.status_code} - {response.text}"
                )
                return None

            contact_data = response.json()
            current_tags = contact_data.get("tags", [])

            # Add new tag if not already present
            if tag not in current_tags:
                updated_tags = current_tags + [tag]

                # Update contact with new tags
                update_payload = {"locationId": GHL_LOCATION_ID, "tags": updated_tags}

                update_response = await client.put(
                    endpoint, headers=headers, json=update_payload
                )

                if update_response.status_code == 200:
                    print(f"✅ Successfully added tag '{tag}' to contact")
                    return True
                else:
                    print(
                        f"❌ Failed to add tag: {update_response.status_code} - {update_response.text}"
                    )
                    return False
            else:
                print(f"ℹ️  Tag '{tag}' already exists on contact")
                return True

    except Exception as e:
        print(f"❌ Error adding tag: {str(e)}")
        return False


async def test_token_refresh():
    """Test the token refresh functionality."""
    print("\n🔄 Testing token refresh...")
    try:
        result = await token_manager.force_refresh()
        print(f"✅ Token refresh successful")
        print(f"New token expires in: {result.get('expires_in', 'N/A')} seconds")
        return True
    except Exception as e:
        print(f"❌ Token refresh failed: {str(e)}")
        return False


async def test_ghl_service_integration():
    """Test the GHL service integration with automatic token refresh."""
    print("\n🧪 Testing GHL Service Integration...")
    
    from .ghl_service import create_ghl_contact, SignupType
    
    # Test data
    test_contact = GHLContactData(
        email="test@example.com",
        first_name="Test User",
        tags=["test", "integration"]
    )
    
    try:
        result = await create_ghl_contact(test_contact)
        print(f"✅ GHL service integration test successful")
        print(f"Result: {result}")
        return True
    except Exception as e:
        print(f"❌ GHL service integration test failed: {str(e)}")
        return False


async def run_comprehensive_tests():
    """Run a comprehensive test suite for GHL integration."""
    print("\n===== Comprehensive GoHighLevel Integration Test =====\n")

    test_results = {
        "token_refresh": False,
        "connection": False,
        "get_contacts": False,
        "create_contact": False,
        "service_integration": False,
    }

    # Test 1: Token refresh
    print("1. Testing token refresh...")
    test_results["token_refresh"] = await test_token_refresh()

    # Test 2: Connection test
    print("\n2. Testing API connection...")
    test_results["connection"] = await test_connection()

    # Test 3: Get contacts
    print("\n3. Testing get contacts...")
    contacts = await get_contacts(5)
    test_results["get_contacts"] = contacts is not None

    # Test 4: Create test contact
    print("\n4. Testing contact creation...")
    test_contact = await create_test_contact(
        "integration.test@example.com", "Integration", "Test"
    )
    test_results["create_contact"] = test_contact is not None

    # Test 5: Service integration
    print("\n5. Testing service integration...")
    test_results["service_integration"] = await test_ghl_service_integration()

    # Print summary
    print("\n===== Test Results Summary =====")
    passed = sum(test_results.values())
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! GHL integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the configuration and logs.")
    
    return test_results


async def run_tests():
    """Legacy function for backward compatibility."""
    return await run_comprehensive_tests()


# Run tests directly
if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())
