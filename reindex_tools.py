import requests


def reindex_all_tools():
    """
    Reindex all tools from MongoDB to Algolia
    """
    url = "http://localhost:8000/api/search/index/tools"

    try:
        response = requests.post(url)
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 202:
            print("✅ Successfully started reindexing tools to Algolia")
        else:
            print(f"❌ Error: Received status code {response.status_code}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    reindex_all_tools()
