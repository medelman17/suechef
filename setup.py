"""Setup script for the unified legal MCP system."""

import asyncio
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import neo4j
import os

from database_schema import POSTGRES_SCHEMA, QDRANT_COLLECTIONS


async def setup_postgres():
    """Initialize PostgreSQL database and schema."""
    print("Setting up PostgreSQL...")
    
    # Create database if it doesn't exist
    try:
        # Connect to default database
        conn = await asyncpg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", 5432),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            database="postgres"
        )
        
        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'legal_research'"
        )
        
        if not exists:
            await conn.execute("CREATE DATABASE legal_research")
            print("Created database: legal_research")
        
        await conn.close()
    except Exception as e:
        print(f"Error creating database: {e}")
    
    # Connect to legal_research database and create schema
    pool = await asyncpg.create_pool(
        os.getenv("POSTGRES_URL", "postgresql://localhost/legal_research")
    )
    
    async with pool.acquire() as conn:
        await conn.execute(POSTGRES_SCHEMA)
        print("PostgreSQL schema created successfully")
    
    await pool.close()


def setup_qdrant():
    """Initialize Qdrant collections."""
    print("Setting up Qdrant...")
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    
    for collection_name, config in QDRANT_COLLECTIONS.items():
        try:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=config["size"],
                    distance=Distance[config["distance"].upper()]
                )
            )
            print(f"Created Qdrant collection: {collection_name}")
        except Exception as e:
            print(f"Collection {collection_name} might already exist: {e}")


def test_neo4j():
    """Test Neo4j connection."""
    print("Testing Neo4j connection...")
    
    try:
        driver = neo4j.GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
        )
        
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            if result.single()["test"] == 1:
                print("Neo4j connection successful")
        
        driver.close()
    except Exception as e:
        print(f"Neo4j connection error: {e}")
        print("Make sure Neo4j is running and credentials are correct")


async def main():
    """Run all setup steps."""
    print("=== Unified Legal MCP Setup ===\\n")
    
    # PostgreSQL setup
    await setup_postgres()
    print()
    
    # Qdrant setup
    setup_qdrant()
    print()
    
    # Neo4j test
    test_neo4j()
    print()
    
    print("Setup complete!")
    print("\\nEnvironment variables to set:")
    print("- POSTGRES_URL (default: postgresql://localhost/legal_research)")
    print("- QDRANT_URL (default: http://localhost:6333)")
    print("- NEO4J_URI (default: bolt://localhost:7687)")
    print("- NEO4J_USER (default: neo4j)")
    print("- NEO4J_PASSWORD (required)")
    print("- OPENAI_API_KEY (required for embeddings)")


if __name__ == "__main__":
    asyncio.run(main())