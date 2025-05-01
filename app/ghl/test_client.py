"""
Test client for interacting with the GoHighLevel API directly
Used for debugging and testing the integration
"""

import httpx
import json
import os
from typing import Dict, Any, Optional, List
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GoHighLevel API Configuration
GHL_API_KEY = os.getenv("GHL_API_KEY", "")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "")
GHL_BASE_URL = "https://services.leadconnectorhq.com"


async def test_connection():
    """Test the connection to GoHighLevel API"""
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": "2020-01-01",
        "Content-Type": "application/json",
    }

    if not GHL_API_KEY or not GHL_LOCATION_ID:
        print("⚠️ GHL_API_KEY or GHL_LOCATION_ID not configured")
        return False

    try:
        # Test endpoint that returns location info
        endpoint = f"{GHL_BASE_URL}/locations/{GHL_LOCATION_ID}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                endpoint,
                headers=headers,
            )

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
    """Get contacts from GoHighLevel"""
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": "2020-01-01",
        "Content-Type": "application/json",
    }

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
    """Create a test contact in GoHighLevel"""
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": "2020-01-01",
        "Content-Type": "application/json",
    }

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
    """Add a tag to a contact in GoHighLevel"""
    headers = {
        "Authorization": f"Bearer {GHL_API_KEY}",
        "Version": "2020-01-01",
        "Content-Type": "application/json",
    }

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

            # Add new tag
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

    except Exception as e:
        print(f"❌ Error adding tag: {str(e)}")
        return False


async def run_tests():
    """Run a series of tests to verify GoHighLevel integration"""
    print("\n===== GoHighLevel Integration Test =====\n")

    # Test connection
    connection_successful = await test_connection()
    if not connection_successful:
        print("\n⚠️ Connection failed. Check your API key and location ID.")
        return

    print("\n----- Testing Contact Operations -----\n")

    # Generate a unique email for test
    import uuid

    test_email = f"test-{uuid.uuid4().hex[:8]}@taaft-integration.com"

    # Create a test contact
    print(f"Creating test contact with email: {test_email}")
    contact = await create_test_contact(
        email=test_email, first_name="Test", last_name="User"
    )

    if not contact:
        print("\n⚠️ Failed to create test contact. Aborting remaining tests.")
        return

    # Get the contact ID
    contact_id = contact.get("id")

    # Add a tag to the contact
    print("\nAdding tag to test contact...")
    tag_result = await add_tag_to_contact(contact_id, "Integration Test Passed")

    # Get contacts to verify
    print("\nRetrieving contacts to verify operations...")
    await get_contacts(5)

    print("\n===== Test Complete =====\n")


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(run_tests())
