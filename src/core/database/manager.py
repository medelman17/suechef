"""Database connection manager for SueChef."""

import asyncio
import logging
from typing import Optional
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
import neo4j

from ...config.settings import DatabaseConfig

logger = logging.getLogger(__name__)


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
        """Initialize all database connections with retry logic."""
        if self._initialized:
            return
        
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Initializing database connections (attempt {attempt + 1}/{max_retries})")
                
                # Initialize PostgreSQL with connection pool settings
                self.postgres_pool = await asyncpg.create_pool(
                    self.config.postgres_url,
                    min_size=2,           # Minimum connections
                    max_size=10,          # Maximum connections  
                    max_queries=50000,    # Max queries per connection
                    max_inactive_connection_lifetime=300,  # 5 minutes
                    command_timeout=30    # 30 second timeout
                )
                
                # Test PostgreSQL connection
                async with self.postgres_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                logger.info("✅ PostgreSQL connection established")
                
                # Initialize Qdrant
                self.qdrant_client = QdrantClient(url=self.config.qdrant_url)
                # Test Qdrant connection
                self.qdrant_client.get_collections()
                logger.info("✅ Qdrant connection established")
                
                # Initialize Neo4j
                self.neo4j_driver = neo4j.GraphDatabase.driver(
                    self.config.neo4j_uri,
                    auth=(self.config.neo4j_user, self.config.neo4j_password),
                    max_connection_lifetime=30 * 60,  # 30 minutes
                    max_connection_pool_size=50,
                    connection_acquisition_timeout=30  # 30 seconds
                )
                
                # Test Neo4j connection
                with self.neo4j_driver.session() as session:
                    session.run("RETURN 1")
                logger.info("✅ Neo4j connection established")
                
                # Initialize Graphiti
                self.graphiti_client = Graphiti(
                    uri=self.config.neo4j_uri,
                    user=self.config.neo4j_user,
                    password=self.config.neo4j_password
                )
                
                # CRITICAL: Build indices and constraints after initialization
                await self.graphiti_client.build_indices_and_constraints()
                logger.info("✅ Graphiti initialized with indices and constraints")
                
                self._initialized = True
                logger.info("🎉 All database connections initialized successfully")
                return
                
            except Exception as e:
                logger.error(f"❌ Database initialization attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("💥 All database initialization attempts failed")
                    raise ConnectionError(f"Failed to initialize databases after {max_retries} attempts: {e}")
    
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