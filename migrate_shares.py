import asyncio
import os
import sys
from pathlib import Path

# Add the project root to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir
sys.path.append(str(project_root))

# Now we can import from app
from app.migrations.migrate_shares import migrate_shares_to_tool_unique_id


async def main():
    print("Starting shares migration...")
    await migrate_shares_to_tool_unique_id()
    print("Shares migration completed!")


if __name__ == "__main__":
    asyncio.run(main())
