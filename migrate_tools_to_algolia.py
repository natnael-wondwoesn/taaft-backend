#!/usr/bin/env python3
"""
Entry point script to migrate MongoDB tools collection to Algolia.
This script invokes the app.algolia.migrater.tools_to_algolia module.

Usage:
    python migrate_tools_to_algolia.py
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main():
    """Run the migration script"""
    try:
        logger.info("Starting tools migration to Algolia...")

        # Import and run the migration module
        from app.algolia.migrater.tools_to_algolia import main as run_migration

        run_migration()

        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
