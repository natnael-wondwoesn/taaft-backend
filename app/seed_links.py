#!/usr/bin/env python
"""
Seed script to add AI-related links to the site queue
Run this script to populate the site queue with a list of curated AI websites
"""

import asyncio
import logging
import datetime
from .queue.models import SiteCreate, SitePriority
from .queue.site_queue_manager import SiteQueueManager
from .logger import logger
from .database.setup import setup_database
from .queue.database import get_sites_collection

# List of links to seed, organized by category
SEED_LINKS = [
    # 1. AI Company Websites (Direct Product Pages)
    {
        "name": "OpenAI",
        "url": "https://openai.com",
        "priority": SitePriority.HIGH,
        "category": "AI Products",
        "tags": ["ai", "chatgpt", "gpt", "dall-e", "whisper"],
    },
    {
        "name": "Runway ML",
        "url": "https://runwayml.com",
        "priority": SitePriority.HIGH,
        "category": "AI Products",
        "tags": ["ai", "video", "generative"],
    },
    {
        "name": "Copy.ai",
        "url": "https://copy.ai",
        "priority": SitePriority.MEDIUM,
        "category": "AI Products",
        "tags": ["ai", "writing", "copywriting"],
    },
    {
        "name": "Notion AI",
        "url": "https://notion.so",
        "priority": SitePriority.MEDIUM,
        "category": "AI Products",
        "tags": ["ai", "writing", "productivity"],
    },
    {
        "name": "Jasper",
        "url": "https://jasper.ai",
        "priority": SitePriority.MEDIUM,
        "category": "AI Products",
        "tags": ["ai", "writing", "marketing"],
    },
    {
        "name": "Midjourney",
        "url": "https://midjourney.com",
        "priority": SitePriority.HIGH,
        "category": "AI Products",
        "tags": ["ai", "image", "generative"],
    },
    # 2. Specialized AI Marketplaces
    {
        "name": "Hugging Face",
        "url": "https://huggingface.co",
        "priority": SitePriority.HIGH,
        "category": "AI Marketplaces",
        "tags": ["ai", "models", "datasets", "hub"],
    },
    {
        "name": "OpenAI API",
        "url": "https://platform.openai.com",
        "priority": SitePriority.HIGH,
        "category": "AI Marketplaces",
        "tags": ["ai", "api", "plugins"],
    },
    {
        "name": "Azure AI",
        "url": "https://cognitive.microsoft.com",
        "priority": SitePriority.MEDIUM,
        "category": "AI Marketplaces",
        "tags": ["ai", "azure", "microsoft"],
    },
    {
        "name": "Meta AI",
        "url": "https://ai.facebook.com/tools",
        "priority": SitePriority.MEDIUM,
        "category": "AI Marketplaces",
        "tags": ["ai", "meta", "facebook"],
    },
    {
        "name": "Replicate",
        "url": "https://replicate.com",
        "priority": SitePriority.MEDIUM,
        "category": "AI Marketplaces",
        "tags": ["ai", "models", "api"],
    },
    {
        "name": "Papers with Code",
        "url": "https://paperswithcode.com",
        "priority": SitePriority.MEDIUM,
        "category": "AI Marketplaces",
        "tags": ["ai", "research", "papers", "code"],
    },
    # 3. Product Listing Sites
    {
        "name": "Product Hunt",
        "url": "https://www.producthunt.com",
        "priority": SitePriority.MEDIUM,
        "category": "Product Listings",
        "tags": ["products", "startups", "tech"],
    },
    {
        "name": "G2",
        "url": "https://www.g2.com",
        "priority": SitePriority.MEDIUM,
        "category": "Product Listings",
        "tags": ["reviews", "business", "software"],
    },
    {
        "name": "Capterra",
        "url": "https://www.capterra.com",
        "priority": SitePriority.MEDIUM,
        "category": "Product Listings",
        "tags": ["reviews", "business", "software"],
    },
    {
        "name": "GetApp",
        "url": "https://www.getapp.com",
        "priority": SitePriority.MEDIUM,
        "category": "Product Listings",
        "tags": ["reviews", "business", "software"],
    },
    {
        "name": "AlternativeTo",
        "url": "https://alternativeto.net",
        "priority": SitePriority.MEDIUM,
        "category": "Product Listings",
        "tags": ["alternatives", "software", "apps"],
    },
    # 4. GitHub Repositories
    {
        "name": "GitHub AI",
        "url": "https://github.com",
        "priority": SitePriority.HIGH,
        "category": "Code Repositories",
        "tags": ["ai", "machine-learning", "llm", "open-source"],
    },
    # 5. News Sites (for Recent Announcements)
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/tag/artificial-intelligence",
        "priority": SitePriority.MEDIUM,
        "category": "News",
        "tags": ["ai", "news", "startups"],
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai",
        "priority": SitePriority.MEDIUM,
        "category": "News",
        "tags": ["ai", "news", "business"],
    },
    {
        "name": "Analytics Vidhya",
        "url": "https://www.analyticsvidhya.com",
        "priority": SitePriority.LOW,
        "category": "News",
        "tags": ["ai", "analytics", "data-science"],
    },
    {
        "name": "MarkTechPost",
        "url": "https://www.marktechpost.com",
        "priority": SitePriority.LOW,
        "category": "News",
        "tags": ["ai", "news", "research"],
    },
    {
        "name": "The Next Web",
        "url": "https://thenextweb.com",
        "priority": SitePriority.LOW,
        "category": "News",
        "tags": ["tech", "news", "startups"],
    },
    {
        "name": "Google AI Blog",
        "url": "https://ai.googleblog.com",
        "priority": SitePriority.MEDIUM,
        "category": "News",
        "tags": ["ai", "google", "research"],
    },
    # 6. Competitor Directories (Validation Only)
    {
        "name": "Futurepedia",
        "url": "https://www.futurepedia.io",
        "priority": SitePriority.LOW,
        "category": "AI Directories",
        "tags": ["ai", "directory", "tools"],
    },
    {
        "name": "AI For That",
        "url": "https://www.aiforthat.com",
        "priority": SitePriority.LOW,
        "category": "AI Directories",
        "tags": ["ai", "directory", "tools"],
    },
    {
        "name": "Toolify",
        "url": "https://www.toolify.ai",
        "priority": SitePriority.LOW,
        "category": "AI Directories",
        "tags": ["ai", "directory", "tools"],
    },
    {
        "name": "There's An AI For That",
        "url": "https://theresanaiforthat.com",
        "priority": SitePriority.LOW,
        "category": "AI Directories",
        "tags": ["ai", "directory", "tools"],
    },
]


async def seed_sites():
    """Seed the site queue with the predefined links"""
    # Ensure database is set up
    await setup_database()

    # Get sites collection
    sites_collection = await get_sites_collection()

    # Create site queue manager
    manager = SiteQueueManager(sites_collection)

    # Add each site to the queue
    success_count = 0
    failure_count = 0
    skipped_count = 0

    for site_data in SEED_LINKS:
        # Check if site already exists (by URL)
        existing_site = await sites_collection.find_one({"url": site_data["url"]})
        if existing_site:
            logger.info(f"Skipping {site_data['name']} - already exists in the queue")
            skipped_count += 1
            continue

        try:
            # Create site model and add to queue
            site = SiteCreate(**site_data)
            created_site = await manager.add_site(site)

            if created_site:
                logger.info(f"Added {site_data['name']} to queue successfully")
                success_count += 1
            else:
                logger.error(f"Failed to add {site_data['name']} - unknown error")
                failure_count += 1

        except Exception as e:
            logger.error(f"Error adding {site_data['name']}: {str(e)}")
            failure_count += 1

    # Print summary
    logger.info(
        f"Seeding complete. Added: {success_count}, Failed: {failure_count}, Skipped: {skipped_count}"
    )


async def main():
    """Main function to run the seed script."""
    # Seed sites
    await seed_sites()


if __name__ == "__main__":
    # Run the seed script
    asyncio.run(main())
