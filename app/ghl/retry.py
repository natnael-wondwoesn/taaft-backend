# app/ghl/retry.py
import json
import asyncio
from .ghl_service import GHLContactData, create_ghl_contact
from ..logger import logger


async def retry_failed_signups():
    try:
        with open("failed_ghl_signups.txt", "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.info("No failed GHL signups to retry")
        return

    with open("failed_ghl_signups.txt", "w") as f:
        for line in lines:
            try:
                ghl_data = GHLContactData(**json.loads(line))
                await create_ghl_contact(ghl_data)
                logger.info(f"Retried GHL contact for {ghl_data.email}")
            except Exception as e:
                logger.error(f"Retry failed for {ghl_data.email}: {str(e)}")
                f.write(line)


# Run manually or via cron
if __name__ == "__main__":
    asyncio.run(retry_failed_signups())
