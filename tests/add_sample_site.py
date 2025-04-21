"""
Add a sample site to the database that includes the fields
needed for the n8n data format
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base URL for the API (from environment or default to localhost)
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def add_sample_site():
    """Add a sample site with basic fields"""
    url = f"{BASE_URL}/api/sites/"

    # Sample site data
    payload = {
        "name": "Example Site",
        "url": "https://theresanaiforthat.com/*",
        "priority": "medium",
        "description": "An example site for testing n8n integration",
        "category": "6806415d856a3a9ff0979444",  # Important for n8n format
        "tags": ["test", "example", "n8n"],
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)

        # Print the response
        print(f"Status Code: {response.status_code}")

        if response.ok:
            print("Success! Added site:")
            print(json.dumps(response.json(), indent=2))

            # Test retrieving the site in n8n format
            print("\nTesting n8n data format:")
            test_n8n_format()
        else:
            print(f"Error: {response.text}")

        return response.ok
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False


def test_n8n_format():
    """Test retrieving data in n8n format"""
    n8n_url = f"{BASE_URL}/api/sites/n8n"

    try:
        response = requests.get(n8n_url)

        if response.ok:
            data = response.json()
            if data:
                print(f"Success! Retrieved {len(data)} sites in n8n format.")
                print("\nExpected n8n format:")
                print(
                    json.dumps(
                        {
                            "_id": {"$oid": "680685e2856a3a9ff097944c"},
                            "link": "https://theresanaiforthat.com/*",
                            "category_id": "6806415d856a3a9ff0979444",
                        },
                        indent=2,
                    )
                )

                print("\nActual data (first site):")
                print(json.dumps(data[0], indent=2))
            else:
                print("No sites found in n8n format.")
        else:
            print(f"Error retrieving n8n format: {response.text}")
    except Exception as e:
        print(f"Exception testing n8n format: {str(e)}")


if __name__ == "__main__":
    print("Adding sample site...")

    # Run the function
    success = add_sample_site()

    if success:
        print("\nSample site added successfully.")
    else:
        print("\nFailed to add sample site.")
