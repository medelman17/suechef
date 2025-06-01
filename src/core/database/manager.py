"""Database connection manager for SueChef."""

import asyncio
from typing import Optional
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
import neo4j

from ...config.settings import DatabaseConfig


class DatabaseManager:
    """Manages all database connections and lifecycle."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.postgres_pool: Optional[asyncpg.Pool] = None
        self.qdrant_client: Optional[QdrantClient] = None
        self.graphiti_client: Optional[Graphiti] = None
        self.neo4j_driver: Optional[neo4j.Driver] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize all database connections."""
        if self._initialized:
            return
        
        # Initialize PostgreSQL
        self.postgres_pool = await asyncpg.create_pool(self.config.postgres_url)
        
        # Initialize Qdrant
        self.qdrant_client = QdrantClient(url=self.config.qdrant_url)
        
        # Initialize Neo4j
        self.neo4j_driver = neo4j.GraphDatabase.driver(
            self.config.neo4j_uri,
            auth=(self.config.neo4j_user, self.config.neo4j_password)
        )
        
        # Initialize Graphiti
        self.graphiti_client = Graphiti(
            uri=self.config.neo4j_uri,
            user=self.config.neo4j_user,
            password=self.config.neo4j_password
        )
        
        # CRITICAL: Build indices and constraints after initialization
        await self.graphiti_client.build_indices_and_constraints()
        
        self._initialized = True
    
    async def close(self):
        """Close all database connections."""
        if not self._initialized:
            return
        
        # Close connections in reverse order
        if self.graphiti_client:
            await self.graphiti_client.close()
        
        if self.neo4j_driver:
            self.neo4j_driver.close()
        
        if self.postgres_pool:
            await self.postgres_pool.close()
        
        # Qdrant client doesn't need explicit closing
        
        self._initialized = False
    
    def ensure_initialized(self):
        """Ensure the database manager is initialized."""
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
    
    @property
    def postgres(self) -> asyncpg.Pool:
        """Get PostgreSQL connection pool."""
        self.ensure_initialized()
        return self.postgres_pool
    
    @property
    def qdrant(self) -> QdrantClient:
        """Get Qdrant client."""
        self.ensure_initialized()
        return self.qdrant_client
    
    @property
    def graphiti(self) -> Graphiti:
        """Get Graphiti client."""
        self.ensure_initialized()
        return self.graphiti_client
    
    @property
    def neo4j(self) -> neo4j.Driver:
        """Get Neo4j driver."""
        self.ensure_initialized()
        return self.neo4j_driver