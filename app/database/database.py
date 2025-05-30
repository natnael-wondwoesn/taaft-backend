from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
# print(MONGODB_URL)

# Create a new client and connect to the server
client = AsyncIOMotorClient(MONGODB_URL, server_api=ServerApi("1"))

# Database will be initialized in the lifespan context
database = client.get_database("taaft_db")


# Export MongoDB operations through this module
async def list_collection_names():
    return await database.list_collection_names()


async def create_collection(name):
    return await database.create_collection(name)


# Chat collections
chat_sessions = database.get_collection("chat_sessions")
chat_messages = database.get_collection("chat_messages")

# User collections
users = database.get_collection("users")

# Tools collection
tools = database.get_collection("tools")

# Sites queue collection
sites = database.get_collection("sites")

# Glossary terms collection
glossary_terms = database.get_collection("glossary_terms")

# Keywords collection
keywords = database.get_collection("keywords")

# Blog articles collection
blog_articles = database.get_collection("blogs")

# Favorites collection
favorites = database.get_collection("favorites")

# Shares collection
shares = database.get_collection("shares")

# Tool click logs collection
tool_clicks = database.get_collection("tool_clicks")
