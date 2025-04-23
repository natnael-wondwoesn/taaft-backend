"""
Seed script for glossary terms.
This script populates the database with initial glossary terms.
"""

import asyncio
import datetime
from .database.database import glossary_terms
from .logger import logger
from .database.setup import setup_database

# Sample glossary terms based on the UI screenshot
SAMPLE_TERMS = [
    {
        "name": "AI",
        "definition": "Artificial Intelligence is intelligence demonstrated by machines, as opposed to natural intelligence displayed by animals and humans.",
        "related_terms": ["Machine Learning", "Deep Learning", "Neural Networks"],
        "tool_references": [],
        "categories": ["Core Concepts"],
        "first_letter": "A",
    },
    {
        "name": "API",
        "definition": "Application Programming Interface is a set of definitions and protocols for building and integrating application software.",
        "related_terms": ["REST", "GraphQL", "Webhooks"],
        "tool_references": [],
        "categories": ["Web Development"],
        "first_letter": "A",
    },
    {
        "name": "Big Data",
        "definition": "Big data refers to extremely large datasets that may be analyzed computationally to reveal patterns, trends, and associations.",
        "related_terms": ["Data Science", "Analytics", "Hadoop"],
        "tool_references": [],
        "categories": ["Data"],
        "first_letter": "B",
    },
    {
        "name": "Chatbot",
        "definition": "A computer program designed to simulate conversation with human users, especially over the internet.",
        "related_terms": ["Natural Language Processing", "AI"],
        "tool_references": [],
        "categories": ["AI Applications"],
        "first_letter": "C",
    },
    {
        "name": "Cloud Computing",
        "definition": "The practice of using a network of remote servers hosted on the internet to store, manage, and process data.",
        "related_terms": ["SaaS", "PaaS", "IaaS"],
        "tool_references": [],
        "categories": ["Infrastructure"],
        "first_letter": "C",
    },
    {
        "name": "Data Science",
        "definition": "An interdisciplinary field that uses scientific methods, processes, algorithms and systems to extract knowledge from structured and unstructured data.",
        "related_terms": ["Machine Learning", "Statistics", "Big Data"],
        "tool_references": [],
        "categories": ["Data"],
        "first_letter": "D",
    },
    {
        "name": "Machine Learning",
        "definition": "The study of computer algorithms that improve automatically through experience and by the use of data.",
        "related_terms": [
            "Deep Learning",
            "Supervised Learning",
            "Unsupervised Learning",
        ],
        "tool_references": [],
        "categories": ["AI Techniques"],
        "first_letter": "M",
    },
    {
        "name": "NLP",
        "definition": "Natural Language Processing is a subfield of linguistics, computer science, and artificial intelligence concerned with the interactions between computers and human language.",
        "related_terms": ["Machine Learning", "Text Analysis", "Sentiment Analysis"],
        "tool_references": [],
        "categories": ["AI Techniques"],
        "first_letter": "N",
    },
]


async def seed_glossary_terms():
    """Seed the database with sample glossary terms."""
    # First check if we already have terms
    count = await glossary_terms.count_documents({})

    if count > 0:
        logger.info(f"Glossary already contains {count} terms. Skipping seeding.")
        return

    # Add timestamps to all terms
    now = datetime.datetime.utcnow()
    for term in SAMPLE_TERMS:
        term["created_at"] = now
        term["updated_at"] = now

    # Insert all terms
    await glossary_terms.insert_many(SAMPLE_TERMS)
    logger.info(f"Seeded {len(SAMPLE_TERMS)} glossary terms.")


async def main():
    """Main function to run the seed script."""
    # Ensure database is set up
    await setup_database()

    # Seed glossary terms
    await seed_glossary_terms()


if __name__ == "__main__":
    # Run the seed script
    asyncio.run(main())
