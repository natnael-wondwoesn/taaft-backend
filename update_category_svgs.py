#!/usr/bin/env python3
"""
Script to update categories in the database with SVG icons
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import Dict, List

# MongoDB connection string from environment or default to localhost
MONGODB_URI = os.environ.get("MONGODB_URL", "mongodb://localhost:27017")

# Connect to MongoDB
client = AsyncIOMotorClient(MONGODB_URI)
db = client.get_database("taaft_db")
categories_collection = db.get_collection("categories")

# SVG definitions for different categories
CATEGORY_SVGS = {
    # Already provided SVGs
    "code": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_5275)"/>
<path d="M37.3335 40L45.3335 32L37.3335 24" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M26.6665 24L18.6665 32L26.6665 40" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_5275" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "image": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_751)"/>
<path d="M41.3333 20H22.6667C21.1939 20 20 21.1939 20 22.6667V41.3333C20 42.8061 21.1939 44 22.6667 44H41.3333C42.8061 44 44 42.8061 44 41.3333V22.6667C44 21.1939 42.8061 20 41.3333 20Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M28.0002 30.6667C29.4729 30.6667 30.6668 29.4728 30.6668 28C30.6668 26.5273 29.4729 25.3334 28.0002 25.3334C26.5274 25.3334 25.3335 26.5273 25.3335 28C25.3335 29.4728 26.5274 30.6667 28.0002 30.6667Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M44 36L39.8853 31.8854C39.3853 31.3855 38.7071 31.1046 38 31.1046C37.2929 31.1046 36.6147 31.3855 36.1147 31.8854L24 44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_751" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "chat": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_691)"/>
<path d="M44 36C44 36.7072 43.719 37.3855 43.219 37.8856C42.7189 38.3857 42.0406 38.6667 41.3333 38.6667H25.3333L20 44V22.6667C20 21.9594 20.281 21.2811 20.781 20.781C21.2811 20.281 21.9594 20 22.6667 20H41.3333C42.0406 20 42.7189 20.281 43.219 20.781C43.719 21.2811 44 21.9594 44 22.6667V36Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_691" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    # Additional SVGs with matching styling
    "marketing": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1000)"/>
<path d="M32 20L36 28H44L38 34L40 42L32 38L24 42L26 34L20 28H28L32 20Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1000" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "e-commerce": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1001)"/>
<path d="M24 24H40L44 36H20L24 24Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M24 44C25.4728 44 26.6667 42.8061 26.6667 41.3333C26.6667 39.8606 25.4728 38.6667 24 38.6667C22.5272 38.6667 21.3333 39.8606 21.3333 41.3333C21.3333 42.8061 22.5272 44 24 44Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M40 44C41.4728 44 42.6667 42.8061 42.6667 41.3333C42.6667 39.8606 41.4728 38.6667 40 38.6667C38.5272 38.6667 37.3333 39.8606 37.3333 41.3333C37.3333 42.8061 38.5272 44 40 44Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1001" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "analytics": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1002)"/>
<path d="M20 44H44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M24 36V44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M32 28V44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M40 20V44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1002" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "content": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1003)"/>
<path d="M38.6667 20H25.3333C24.597 20 24 20.597 24 21.3333V42.6667C24 43.403 24.597 44 25.3333 44H38.6667C39.403 44 40 43.403 40 42.6667V21.3333C40 20.597 39.403 20 38.6667 20Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M28 28H36" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M28 36H36" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1003" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "design": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1004)"/>
<path d="M32 44C38.6274 44 44 38.6274 44 32C44 25.3726 38.6274 20 32 20C25.3726 20 20 25.3726 20 32C20 38.6274 25.3726 44 32 44Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M20 32H44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M32 20C35.1826 23.4589 36.9565 28.1218 37 32.9291C36.9565 37.7364 35.1826 42.3993 32 45.8582" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M32 20C28.8174 23.4589 27.0435 28.1218 27 32.9291C27.0435 37.7364 28.8174 42.3993 32 45.8582" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1004" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "productivity": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1005)"/>
<path d="M32 20V32L40 36" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M32 44C38.6274 44 44 38.6274 44 32C44 25.3726 38.6274 20 32 20C25.3726 20 20 25.3726 20 32C20 38.6274 25.3726 44 32 44Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1005" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "research": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1006)"/>
<path d="M38.6667 38.6667L44 44" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M30.6667 38.6667C35.0849 38.6667 38.6667 35.0849 38.6667 30.6667C38.6667 26.2485 35.0849 22.6667 30.6667 22.6667C26.2485 22.6667 22.6667 26.2485 22.6667 30.6667C22.6667 35.0849 26.2485 38.6667 30.6667 38.6667Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1006" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
    "data": """<svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="64" height="64" rx="32" fill="url(#paint0_linear_564_1007)"/>
<path d="M32 22.6667C36.4183 22.6667 40 24.7462 40 27.3333V36.6667C40 39.2538 36.4183 41.3333 32 41.3333C27.5817 41.3333 24 39.2538 24 36.6667V27.3333C24 24.7462 27.5817 22.6667 32 22.6667Z" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M40 32C40 34.5872 36.4183 36.6667 32 36.6667C27.5817 36.6667 24 34.5872 24 32" stroke="#7E22CE" stroke-width="2.66667" stroke-linecap="round" stroke-linejoin="round"/>
<defs>
<linearGradient id="paint0_linear_564_1007" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
<stop stop-color="#A855F7" stop-opacity="0.3"/>
<stop offset="1" stop-color="#6366F1" stop-opacity="0.3"/>
</linearGradient>
</defs>
</svg>""",
}

# Map to convert between different IDs/formats
CATEGORY_ID_MAPPING = {"software-development": "code", "chat-conversation": "chat"}


async def update_categories_with_svgs() -> None:
    """
    Update all categories in the database to include SVG icons
    """
    print("Updating categories with SVG icons...")

    # Get all categories
    categories = await categories_collection.find().to_list(length=100)

    updated_count = 0
    for category in categories:
        category_id = category["id"]

        # Check if we need to map this category ID to another ID for the SVG
        svg_id = CATEGORY_ID_MAPPING.get(category_id, category_id)

        # Get the appropriate SVG
        svg = CATEGORY_SVGS.get(svg_id)

        if svg:
            # Update the category with the SVG
            result = await categories_collection.update_one(
                {"id": category_id}, {"$set": {"svg": svg}}
            )

            if result.modified_count > 0:
                updated_count += 1
                print(f"Updated category '{category['name']}' with SVG icon")
        else:
            print(
                f"Warning: No SVG found for category '{category['name']}' (id: {category_id})"
            )

    print(f"Updated {updated_count} out of {len(categories)} categories with SVG icons")


async def main() -> None:
    """Main function to run the script"""
    try:
        await update_categories_with_svgs()
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Close the MongoDB connection
        client.close()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
