from loguru import logger
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="1 week",
    level=LOG_LEVEL,
    format="{time} {level} {message}",
)
