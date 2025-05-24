#!/usr/bin/env python3
"""
Script to search job impacts via the API endpoint
Demonstrates how to use the new /api/search/job-impacts endpoint
"""

import requests
import json
import argparse
import os
from dotenv import load_dotenv
from urllib.parse import urlencode

# Load environment variables for API keys
load_dotenv()


def search_job_impacts(
    query=None,
    job_title=None,
    job_category=None,
    min_impact_score=None,
    task_name=None,
    tool_name=None,
    page=1,
    per_page=20,
    sort_by="impact_score",
    base_url="http://localhost:8001",
    api_token=None,
):
    """
    Search for job impacts via the API endpoint

    Args:
        query: General search query
        job_title: Filter by job title
        job_category: Filter by job category
        min_impact_score: Filter by minimum impact score
        task_name: Filter by task name
        tool_name: Filter by tool name
        page: Page number (1-based)
        per_page: Results per page
        sort_by: Sort order (impact_score, relevance, date)
        base_url: Base URL for the API
        api_token: Admin API token for authentication

    Returns:
        Search results from the API
    """
    # Build query parameters
    params = {}
    if query:
        params["query"] = query
    if job_title:
        params["job_title"] = job_title
    if job_category:
        params["job_category"] = job_category
    if min_impact_score is not None:
        params["min_impact_score"] = min_impact_score
    if task_name:
        params["task_name"] = task_name
    if tool_name:
        params["tool_name"] = tool_name
    if page:
        params["page"] = page
    if per_page:
        params["per_page"] = per_page
    if sort_by:
        params["sort_by"] = sort_by

    # Build the URL with query parameters
    url = f"{base_url}/api/search/job-impacts"
    if params:
        url = f"{url}?{urlencode(params)}"

    print(f"Making request to: {url}")

    # Set up headers with authentication if token is provided
    headers = {}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    try:
        # Make the request
        response = requests.get(url, headers=headers)

        # Check for success
        if response.status_code == 200:
            data = response.json()

            # Print summary
            print(f"\nSearch Results Summary:")
            print(f"Found {data.get('total_hits', 0)} job impacts")
            print(f"Showing page {data.get('page', 1)} of {data.get('total_pages', 1)}")
            print(f"Processing time: {data.get('processing_time_ms', 0)}ms")

            # Print each result
            print("\nResults:")
            for i, hit in enumerate(data.get("hits", []), 1):
                print(f"\n--- Result {i} ---")
                print(f"Job Title: {hit.get('job_title', 'N/A')}")
                print(f"Category: {hit.get('job_category', 'N/A')}")
                print(f"Impact Score: {hit.get('ai_impact_score', 'N/A')}")

                # Print tasks (limited to first 3)
                tasks = hit.get("tasks", [])
                if tasks:
                    print(f"Tasks ({len(tasks)} total):")
                    for j, task in enumerate(tasks[:3], 1):
                        print(
                            f"  {j}. {task.get('name', 'N/A')} ({task.get('task_ai_impact_score', 'N/A')})"
                        )
                    if len(tasks) > 3:
                        print(f"  ... and {len(tasks) - 3} more tasks")

                # Print URL
                if "detail_page_link" in hit:
                    print(f"Details: {hit.get('detail_page_link')}")

            # Print pagination info
            if data.get("total_pages", 1) > 1:
                print(
                    f"\nShowing page {data.get('page', 1)} of {data.get('total_pages', 1)}"
                )
                print(f"Use --page parameter to see more results")

            return data
        elif response.status_code == 401:
            print(
                "\n❌ Authentication Error: You need to provide a valid admin API token"
            )
            print(
                "Use the --token parameter or set the ADMIN_API_TOKEN environment variable"
            )
            return None
        elif response.status_code == 403:
            print(
                "\n❌ Authorization Error: Your API token does not have admin privileges"
            )
            print("Contact the system administrator to get proper access")
            return None
        else:
            print(f"\n❌ Error: Received status code {response.status_code}")
            print(f"Response: {response.text}")
            return None

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return None


def main():
    """Parse command line arguments and search job impacts"""
    parser = argparse.ArgumentParser(description="Search job impacts via the API")

    # Add arguments for all search parameters
    parser.add_argument("--query", help="General search query")
    parser.add_argument("--job-title", help="Filter by job title")
    parser.add_argument("--job-category", help="Filter by job category")
    parser.add_argument(
        "--min-impact-score", type=float, help="Filter by minimum impact score"
    )
    parser.add_argument("--task-name", help="Filter by task name")
    parser.add_argument("--tool-name", help="Filter by tool name")
    parser.add_argument("--page", type=int, default=1, help="Page number (1-based)")
    parser.add_argument("--per-page", type=int, default=20, help="Results per page")
    parser.add_argument(
        "--sort-by",
        choices=["impact_score", "relevance", "date"],
        default="impact_score",
        help="Sort order",
    )
    parser.add_argument(
        "--server", default="http://localhost:8001", help="Base URL for the API server"
    )
    parser.add_argument(
        "--token",
        help="Admin API token for authentication (can also be set via ADMIN_API_TOKEN env var)",
    )

    # Parse arguments
    args = parser.parse_args()

    # Get API token from arguments or environment variable
    api_token = args.token or os.getenv("ADMIN_API_TOKEN")

    if not api_token:
        print(
            "\n⚠️ Warning: No API token provided. This endpoint requires admin authentication."
        )
        print(
            "Use the --token parameter or set the ADMIN_API_TOKEN environment variable.\n"
        )

    # Call search function with arguments
    search_job_impacts(
        query=args.query,
        job_title=args.job_title,
        job_category=args.job_category,
        min_impact_score=args.min_impact_score,
        task_name=args.task_name,
        tool_name=args.tool_name,
        page=args.page,
        per_page=args.per_page,
        sort_by=args.sort_by,
        base_url=args.server,
        api_token=api_token,
    )


if __name__ == "__main__":
    main()
