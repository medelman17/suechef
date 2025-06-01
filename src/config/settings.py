"""Centralized configuration management for SueChef."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    postgres_url: str
    qdrant_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str


@dataclass
class APIConfig:
    """External API configuration."""
    openai_api_key: str
    courtlistener_api_key: Optional[str] = None


@dataclass
class MCPConfig:
    """MCP server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    path: str = "/mcp"
    log_level: str = "info"


@dataclass
class SueChefConfig:
    """Main SueChef application configuration."""
    database: DatabaseConfig
    api: APIConfig
    mcp: MCPConfig
    environment: str = "development"


def load_config() -> SueChefConfig:
    """Load configuration from environment variables."""
    
    # Database configuration
    database = DatabaseConfig(
        postgres_url=os.getenv(
            "POSTGRES_URL", 
            "postgresql://postgres:suechef_password@localhost:5432/legal_research"
        ),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password")
    )
    
    # API configuration
    api = APIConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        courtlistener_api_key=os.getenv("COURTLISTENER_API_KEY")
    )
    
    # MCP server configuration
    mcp = MCPConfig(
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8000")),
        path=os.getenv("MCP_PATH", "/mcp"),
        log_level=os.getenv("MCP_LOG_LEVEL", "info")
    )
    
    return SueChefConfig(
        database=database,
        api=api,
        mcp=mcp,
        environment=os.getenv("ENVIRONMENT", "development")
    )


def validate_config(config: SueChefConfig) -> None:
    """Validate configuration and raise errors for missing required settings."""
    
    if not config.api.openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")
    
    if not config.database.postgres_url:
        raise ValueError("POSTGRES_URL environment variable is required")
    
    if not config.database.qdrant_url:
        raise ValueError("QDRANT_URL environment variable is required")
    
    if not config.database.neo4j_uri:
        raise ValueError("NEO4J_URI environment variable is required")


# Global configuration instance
_config: Optional[SueChefConfig] = None


def get_config() -> SueChefConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
        validate_config(_config)
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None