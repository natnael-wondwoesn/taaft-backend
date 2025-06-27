#!/usr/bin/env python3
"""
Jira MCP Server
Provides tools for interacting with Jira tickets through the Model Context Protocol.
"""

import asyncio
import os
from typing import Any, Sequence
import httpx
import base64
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities
import mcp.server.stdio
import mcp.types as types


class JiraClient:
    def __init__(self, base_url: str, username: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token

        # Create basic auth header
        auth_string = f"{username}:{api_token}"
        auth_bytes = auth_string.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        self.headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def search_issues(self, jql: str, max_results: int = 50) -> dict:
        """Search for Jira issues using JQL"""
        async with httpx.AsyncClient() as client:
            params = {
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,description,status,assignee,reporter,priority,created,updated,issuetype",
            }
            response = await client.get(
                f"{self.base_url}/rest/api/3/search",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_issue(self, issue_key: str) -> dict:
        """Get a specific Jira issue by key"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rest/api/3/issue/{issue_key}", headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def update_issue(self, issue_key: str, fields: dict) -> dict:
        """Update a Jira issue"""
        async with httpx.AsyncClient() as client:
            payload = {"fields": fields}
            response = await client.put(
                f"{self.base_url}/rest/api/3/issue/{issue_key}",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return {
                "success": True,
                "message": f"Issue {issue_key} updated successfully",
            }

    async def add_comment(self, issue_key: str, comment: str) -> dict:
        """Add a comment to a Jira issue"""
        async with httpx.AsyncClient() as client:
            payload = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"text": comment, "type": "text"}],
                        }
                    ],
                }
            }
            response = await client.post(
                f"{self.base_url}/rest/api/3/issue/{issue_key}/comment",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def get_transitions(self, issue_key: str) -> dict:
        """Get available transitions for an issue"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()

    async def transition_issue(self, issue_key: str, transition_id: str) -> dict:
        """Transition an issue to a new status"""
        async with httpx.AsyncClient() as client:
            payload = {"transition": {"id": transition_id}}
            response = await client.post(
                f"{self.base_url}/rest/api/3/issue/{issue_key}/transitions",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return {
                "success": True,
                "message": f"Issue {issue_key} transitioned successfully",
            }


# Initialize Jira client
jira_client = None


def format_issue(issue: dict) -> str:
    """Format a Jira issue for display"""
    fields = issue.get("fields", {})

    assignee = fields.get("assignee")
    assignee_name = assignee.get("displayName") if assignee else "Unassigned"

    reporter = fields.get("reporter")
    reporter_name = reporter.get("displayName") if reporter else "Unknown"

    status = fields.get("status", {}).get("name", "Unknown")
    priority = fields.get("priority", {}).get("name", "Unknown")
    issue_type = fields.get("issuetype", {}).get("name", "Unknown")

    description = fields.get("description", "No description")
    if isinstance(description, dict):
        # Handle Atlassian Document Format
        description = extract_text_from_adf(description)

    return f"""
**{issue.get("key")}**: {fields.get("summary", "No title")}

**Type**: {issue_type}
**Status**: {status}
**Priority**: {priority}
**Assignee**: {assignee_name}
**Reporter**: {reporter_name}
**Created**: {fields.get("created", "Unknown")}
**Updated**: {fields.get("updated", "Unknown")}

**Description**:
{description}
"""


def extract_text_from_adf(adf_content: dict) -> str:
    """Extract plain text from Atlassian Document Format"""
    if not isinstance(adf_content, dict):
        return str(adf_content)

    text_parts = []

    def extract_text(node):
        if isinstance(node, dict):
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            elif "content" in node:
                for child in node["content"]:
                    extract_text(child)
        elif isinstance(node, list):
            for item in node:
                extract_text(item)

    extract_text(adf_content)
    return " ".join(text_parts)


# Create server instance
server = Server("jira-mcp-server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Jira tools"""
    return [
        types.Tool(
            name="search_jira_issues",
            description="Search for Jira issues using JQL (Jira Query Language)",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string (e.g., 'project = PROJ AND status = Open')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "default": 50,
                    },
                },
                "required": ["jql"],
            },
        ),
        types.Tool(
            name="get_jira_issue",
            description="Get detailed information about a specific Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., 'PROJ-123')",
                    }
                },
                "required": ["issue_key"],
            },
        ),
        types.Tool(
            name="update_jira_issue",
            description="Update fields of a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., 'PROJ-123')",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Update the issue summary/title",
                    },
                    "description": {
                        "type": "string",
                        "description": "Update the issue description",
                    },
                },
                "required": ["issue_key"],
            },
        ),
        types.Tool(
            name="add_jira_comment",
            description="Add a comment to a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., 'PROJ-123')",
                    },
                    "comment": {"type": "string", "description": "Comment text to add"},
                },
                "required": ["issue_key", "comment"],
            },
        ),
        types.Tool(
            name="get_jira_transitions",
            description="Get available status transitions for a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., 'PROJ-123')",
                    }
                },
                "required": ["issue_key"],
            },
        ),
        types.Tool(
            name="transition_jira_issue",
            description="Change the status of a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "Jira issue key (e.g., 'PROJ-123')",
                    },
                    "transition_id": {
                        "type": "string",
                        "description": "ID of the transition to perform (use get_jira_transitions to see available options)",
                    },
                },
                "required": ["issue_key", "transition_id"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls"""
    if not jira_client:
        return [
            types.TextContent(
                type="text",
                text="Error: Jira client not initialized. Please check your environment variables.",
            )
        ]

    try:
        if name == "search_jira_issues":
            jql = arguments["jql"]
            max_results = arguments.get("max_results", 50)

            result = await jira_client.search_issues(jql, max_results)
            issues = result.get("issues", [])

            if not issues:
                return [
                    types.TextContent(
                        type="text", text=f"No issues found for JQL query: {jql}"
                    )
                ]

            formatted_issues = []
            for issue in issues:
                formatted_issues.append(format_issue(issue))

            response = f"Found {len(issues)} issue(s):\n\n" + "\n---\n".join(
                formatted_issues
            )

            return [types.TextContent(type="text", text=response)]

        elif name == "get_jira_issue":
            issue_key = arguments["issue_key"]
            issue = await jira_client.get_issue(issue_key)

            return [types.TextContent(type="text", text=format_issue(issue))]

        elif name == "update_jira_issue":
            issue_key = arguments["issue_key"]
            fields = {}

            if "summary" in arguments:
                fields["summary"] = arguments["summary"]
            if "description" in arguments:
                fields["description"] = arguments["description"]

            if not fields:
                return [
                    types.TextContent(type="text", text="No fields provided to update")
                ]

            result = await jira_client.update_issue(issue_key, fields)
            return [types.TextContent(type="text", text=result["message"])]

        elif name == "add_jira_comment":
            issue_key = arguments["issue_key"]
            comment = arguments["comment"]

            result = await jira_client.add_comment(issue_key, comment)
            return [
                types.TextContent(
                    type="text", text=f"Comment added successfully to {issue_key}"
                )
            ]

        elif name == "get_jira_transitions":
            issue_key = arguments["issue_key"]
            result = await jira_client.get_transitions(issue_key)

            transitions = result.get("transitions", [])
            if not transitions:
                return [
                    types.TextContent(
                        type="text", text=f"No transitions available for {issue_key}"
                    )
                ]

            transition_list = []
            for transition in transitions:
                transition_list.append(
                    f"- {transition['name']} (ID: {transition['id']})"
                )

            response = f"Available transitions for {issue_key}:\n\n" + "\n".join(
                transition_list
            )
            return [types.TextContent(type="text", text=response)]

        elif name == "transition_jira_issue":
            issue_key = arguments["issue_key"]
            transition_id = arguments["transition_id"]

            result = await jira_client.transition_issue(issue_key, transition_id)
            return [types.TextContent(type="text", text=result["message"])]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    global jira_client

    # Initialize Jira client from environment variables
    base_url = os.getenv("JIRA_BASE_URL")
    username = os.getenv("JIRA_USERNAME")
    api_token = os.getenv("JIRA_API_TOKEN")

    if not all([base_url, username, api_token]):
        print("Error: Missing required environment variables:")
        print("- JIRA_BASE_URL (e.g., https://your-domain.atlassian.net)")
        print("- JIRA_USERNAME (your email)")
        print("- JIRA_API_TOKEN (generate from Atlassian account settings)")
        return

    jira_client = JiraClient(base_url, username, api_token)

    # Create initialization options
    init_options = InitializationOptions(
        server_name="jira-mcp-server",
        server_version="1.0.0",
        capabilities=ServerCapabilities(tools={}),
    )

    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
