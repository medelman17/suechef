"""Database initialization utilities."""

from qdrant_client.models import Distance, VectorParams

from .manager import DatabaseManager
from .schemas import POSTGRES_SCHEMA, QDRANT_COLLECTIONS


async def initialize_databases(db_manager: DatabaseManager):
    """Initialize database schemas and collections."""
    
    # Initialize PostgreSQL schema
    async with db_manager.postgres.acquire() as conn:
        await conn.execute(POSTGRES_SCHEMA)
    
    # Initialize Qdrant collections
    for collection_name, config in QDRANT_COLLECTIONS.items():
        try:
            db_manager.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=config["size"],
                    distance=Distance[config["distance"].upper()]
                )
            )
        except Exception:
            # Collection might already exist
            pass