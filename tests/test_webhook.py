"""
Test the n8n data feed endpoint
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base URL for the API (from environment or default to localhost)
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def test_n8n_data():
    """Test the n8n data feed endpoint"""
    n8n_url = f"{BASE_URL}/api/sites/n8n"

    # Send the request
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.get(n8n_url, headers=headers)

        # Print the response
        print(f"Status Code: {response.status_code}")

        if response.ok:
            data = response.json()
            print(f"Success! Received {len(data)} sites:")

            # Print a sample of expected format
            print("\nExpected format example:")
            sample = {
                "_id": {"$oid": "680685e2856a3a9ff097944c"},
                "link": "https://theresanaiforthat.com/*",
                "category_id": "6806415d856a3a9ff0979444",
            }
            print(json.dumps(sample, indent=2))

            # Print actual received data (up to 5 items)
            print("\nActual received data:")
            for i, site in enumerate(data[:5]):  # Print first 5 sites for brevity
                print(f"\nSite {i+1}:")
                print(json.dumps(site, indent=2))

                # Validate the structure
                validate_n8n_format(site)

            if len(data) > 5:
                print(f"\n... and {len(data) - 5} more sites")
        else:
            print(f"Error: {response.text}")

        return response.ok
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False


def validate_n8n_format(site):
    """Validate that a site follows the required n8n format"""
    required_fields = ["_id", "link", "category_id"]
    missing_fields = [field for field in required_fields if field not in site]

    if missing_fields:
        print(f"Warning: Missing fields in site data: {missing_fields}")

    # Check that the _id field has the proper $oid format
    if "_id" in site and not (isinstance(site["_id"], dict) and "$oid" in site["_id"]):
        print("Warning: _id field doesn't have proper $oid format")


if __name__ == "__main__":
    print("Testing n8n data feed...")

    # Run the test
    success = test_n8n_data()

    if success:
        print("\nn8n data feed test completed successfully.")
    else:
        print("\nn8n data feed test failed.")
