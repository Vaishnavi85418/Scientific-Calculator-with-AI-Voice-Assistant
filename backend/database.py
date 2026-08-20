"""
MongoDB connection and database helpers.
Credentials are read from environment variables — never hardcoded.
"""
import os
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME: str = os.getenv("DATABASE_NAME", "scientific_calculator")

# Module-level client — created once, reused across requests
_client: MongoClient | None = None


def get_client() -> MongoClient:
    """Return (and lazily create) the shared MongoClient."""
    global _client
    if _client is None:
        _client = MongoClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000,  # 5-second connection timeout
            connectTimeoutMS=5000,
        )
    return _client


def get_database():
    """Return the application database."""
    return get_client()[DATABASE_NAME]


def get_calculations_collection() -> Collection:
    """Return the calculations collection, ensuring required indexes exist."""
    db = get_database()
    collection: Collection = db["calculations"]
    # Index on created_at for fast history queries (most-recent first)
    collection.create_index([("created_at", -1)], background=True)
    return collection


def ping_database() -> bool:
    """
    Check whether MongoDB is reachable.
    Returns True on success, False on failure.
    """
    try:
        get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError):
        return False


def close_connection() -> None:
    """Close the MongoDB client (call on application shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
