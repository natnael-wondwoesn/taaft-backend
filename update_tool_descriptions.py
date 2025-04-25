#!/usr/bin/env python3
import asyncio
import time
import argparse
from uuid import UUID
from app.database.database import database, client
from app.logger import logger
from app.chat.llm_service import LLMService


async def generate_description(tool_name: str, tool_link: str) -> str:
    """
    Generate a description for a tool using LLM.
    """
    try:
        # Initialize LLM service
        llm_service = LLMService()

        # Create prompt for the LLM
        prompt = f"""
        Please generate a concise and informative description for the following tool:
        
        Tool Name: {tool_name}
        Tool Link: {tool_link}
        
        The description should explain what the tool does, its main features, and its potential benefits.
        Keep the description under 100 words and make it clear and informative.
        Do not include any marketing language, just factual information.
        """

        # Get response from LLM
        messages = [{"role": "user", "content": prompt}]
        response = await llm_service.get_llm_response(messages)

        # Extract the description from the response
        if isinstance(response, dict) and "message" in response:
            return response["message"].strip()
        return response.strip()
    except Exception as e:
        logger.error(f"Failed to generate description for tool '{tool_name}': {e}")
        return ""


async def generate_keywords(tool_name: str, description: str) -> list:
    """
    Generate keywords for a tool using LLM based on its name and description.
    """
    try:
        # Initialize LLM service
        llm_service = LLMService()

        # Create prompt for the LLM
        prompt = f"""
        Based on the following tool name and description, generate 5-10 relevant keywords.
        Return only the keywords as a comma-separated list.
        
        Tool Name: {tool_name}
        Description: {description}
        
        Example output format: keyword1, keyword2, keyword3, keyword4, keyword5
        """

        # Get response from LLM
        messages = [{"role": "user", "content": prompt}]
        response = await llm_service.get_llm_response(messages)

        # Extract and process the keywords
        if isinstance(response, dict) and "message" in response:
            keywords_text = response["message"].strip()
        else:
            keywords_text = response.strip()

        # Split by comma and clean up each keyword
        keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
        return keywords
    except Exception as e:
        logger.error(f"Failed to generate keywords for tool '{tool_name}': {e}")
        return []


async def update_tool_descriptions(
    batch_size=10,
    rate_limit_delay=1,
    dry_run=False,
    update_descriptions=True,
    update_keywords=True,
    limit=None,
):
    """
    Update tool descriptions and keywords using LLM.

    Args:
        batch_size: Number of tools to process before showing progress
        rate_limit_delay: Delay in seconds between API calls to prevent rate limiting
        dry_run: If True, don't actually update the database
        update_descriptions: If True, update missing descriptions
        update_keywords: If True, update missing keywords
        limit: Maximum number of tools to process (None for all)
    """
    # Connect to MongoDB
    try:
        await client.admin.command("ping")
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Could not connect to MongoDB: {str(e)}")
        raise

    # Get all tools
    tools_collection = database.get_collection("tools")
    total_tools = await tools_collection.count_documents({})
    print(f"Found {total_tools} tools in the database")

    if dry_run:
        print("DRY RUN MODE: No actual updates will be made to the database")

    # Update descriptions if requested
    if update_descriptions:
        # Count tools without description or with empty description
        missing_description_count = await tools_collection.count_documents(
            {
                "$or": [
                    {"description": {"$exists": False}},
                    {"description": ""},
                    {"description": None},
                ]
            }
        )
        print(f"Found {missing_description_count} tools without a description")

        # Find tools with missing descriptions
        if missing_description_count > 0:
            tools_without_description = await tools_collection.find(
                {
                    "$or": [
                        {"description": {"$exists": False}},
                        {"description": ""},
                        {"description": None},
                    ]
                }
            ).to_list(length=None)

            # Apply limit if specified
            if limit:
                tools_without_description = tools_without_description[:limit]
                print(f"Limited to processing {len(tools_without_description)} tools")

            processed_count = 0
            for tool in tools_without_description:
                tool_id = tool.get("_id")
                tool_name = tool.get("name", "Unknown Tool")
                tool_link = tool.get("link", "")

                print(f"Generating description for tool: {tool_name}")
                description = await generate_description(tool_name, tool_link)

                if description:
                    # Generate keywords based on the description if requested
                    keywords = (
                        await generate_keywords(tool_name, description)
                        if update_keywords
                        else []
                    )

                    # Prepare update data
                    update_data = {"description": description}
                    if keywords:
                        update_data["keywords"] = keywords

                    # Update the tool with the generated description and keywords
                    if not dry_run:
                        try:
                            await tools_collection.update_one(
                                {"_id": tool_id}, {"$set": update_data}
                            )
                            print(
                                f"Updated tool '{tool_name}' with description and {len(keywords)} keywords"
                            )
                        except Exception as e:
                            print(f"Error updating tool: {e}")
                    else:
                        print(
                            f"[DRY RUN] Would update tool '{tool_name}' with description and {len(keywords)} keywords"
                        )
                else:
                    print(f"Failed to generate description for tool '{tool_name}'")

                # Increment counter and show progress
                processed_count += 1
                if processed_count % batch_size == 0:
                    print(
                        f"Progress: {processed_count}/{len(tools_without_description)} tools processed"
                    )

                # Apply rate limiting to prevent API abuse
                await asyncio.sleep(rate_limit_delay)

    # Update keywords if requested
    if update_keywords and (not update_descriptions or not limit or limit > 0):
        # Calculate remaining limit if applicable
        remaining_limit = (
            None
            if limit is None
            else (limit - processed_count if "processed_count" in locals() else limit)
        )

        if remaining_limit is not None and remaining_limit <= 0:
            print("Reached processing limit, skipping keyword updates")
        else:
            # Find tools with descriptions but without keywords
            missing_keywords_count = await tools_collection.count_documents(
                {
                    "description": {"$exists": True, "$ne": "", "$ne": None},
                    "$or": [
                        {"keywords": {"$exists": False}},
                        {"keywords": []},
                        {"keywords": None},
                    ],
                }
            )

            if missing_keywords_count > 0:
                print(
                    f"Found {missing_keywords_count} tools with descriptions but without keywords"
                )

                tools_without_keywords = await tools_collection.find(
                    {
                        "description": {"$exists": True, "$ne": "", "$ne": None},
                        "$or": [
                            {"keywords": {"$exists": False}},
                            {"keywords": []},
                            {"keywords": None},
                        ],
                    }
                ).to_list(length=None)

                # Apply limit if specified
                if remaining_limit:
                    tools_without_keywords = tools_without_keywords[:remaining_limit]
                    print(
                        f"Limited to processing {len(tools_without_keywords)} tools for keywords"
                    )

                processed_count = 0
                for tool in tools_without_keywords:
                    tool_id = tool.get("_id")
                    tool_name = tool.get("name", "Unknown Tool")
                    description = tool.get("description", "")

                    print(f"Generating keywords for tool: {tool_name}")
                    keywords = await generate_keywords(tool_name, description)

                    if keywords:
                        # Update the tool with the generated keywords
                        if not dry_run:
                            try:
                                await tools_collection.update_one(
                                    {"_id": tool_id}, {"$set": {"keywords": keywords}}
                                )
                                print(
                                    f"Updated tool '{tool_name}' with {len(keywords)} keywords"
                                )
                            except Exception as e:
                                print(f"Error updating tool keywords: {e}")
                        else:
                            print(
                                f"[DRY RUN] Would update tool '{tool_name}' with {len(keywords)} keywords"
                            )
                    else:
                        print(f"Failed to generate keywords for tool '{tool_name}'")

                    # Increment counter and show progress
                    processed_count += 1
                    if processed_count % batch_size == 0:
                        print(
                            f"Progress: {processed_count}/{len(tools_without_keywords)} tools processed"
                        )

                    # Apply rate limiting to prevent API abuse
                    await asyncio.sleep(rate_limit_delay)

    print("Tool description and keyword update completed")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Update tool descriptions and keywords using LLM"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of tools to process before showing progress (default: 10)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Delay in seconds between API calls to prevent rate limiting (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making actual changes to the database",
    )
    parser.add_argument(
        "--descriptions-only",
        action="store_true",
        help="Only update missing descriptions, not keywords",
    )
    parser.add_argument(
        "--keywords-only",
        action="store_true",
        help="Only update missing keywords, not descriptions",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tools to process (default: no limit)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    # Determine what to update based on args
    update_descriptions = not args.keywords_only
    update_keywords = not args.descriptions_only

    asyncio.run(
        update_tool_descriptions(
            batch_size=args.batch_size,
            rate_limit_delay=args.rate_limit,
            dry_run=args.dry_run,
            update_descriptions=update_descriptions,
            update_keywords=update_keywords,
            limit=args.limit,
        )
    )
