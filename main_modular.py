"""
SueChef MCP Server - Modular Version
A simplified, modular implementation using the new architecture.
"""

import asyncio
from typing import Dict, Any, Optional, List

from fastmcp import FastMCP

# Import new modular components
from src.config.settings import get_config
from src.core.database.manager import DatabaseManager
from src.core.database.initializer import initialize_databases
from src.services.legal.event_service import EventService

# Import legacy tools for features not yet migrated
import legal_tools
import courtlistener_tools
import openai


# Initialize FastMCP server
mcp = FastMCP("suechef")

# Global components
config = None
db_manager = None
event_service = None


async def ensure_initialized():
    """Ensure all components are initialized."""
    global config, db_manager, event_service
    
    if config is None:
        config = get_config()
        
        # Initialize database manager
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()
        
        # Initialize database schemas
        await initialize_databases(db_manager)
        
        # Initialize services
        event_service = EventService(db_manager)


# =============================================================================
# MIGRATED TOOLS (using new modular architecture)
# =============================================================================

@mcp.tool()
async def add_event(
    date: str,
    description: str,
    parties: Optional[List[str]] = None,
    document_source: Optional[str] = None,
    excerpts: Optional[str] = None,
    tags: Optional[List[str]] = None,
    significance: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Add chronology events with automatic vector and knowledge graph storage (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await event_service.create_event(
        date=date,
        description=description,
        parties=parties,
        document_source=document_source,
        excerpts=excerpts,
        tags=tags,
        significance=significance,
        group_id=group_id,
        openai_api_key=config.api.openai_api_key
    )


@mcp.tool()
async def get_event(event_id: str) -> Dict[str, Any]:
    """Get a single event by ID (MODULAR VERSION)."""
    await ensure_initialized()
    return await event_service.get_event(event_id)


@mcp.tool()
async def list_events(
    limit: int = 50,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    parties_filter: Optional[List[str]] = None,
    tags_filter: Optional[List[str]] = None,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """List events with optional filtering (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await event_service.list_events(
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
        parties_filter=parties_filter,
        tags_filter=tags_filter,
        group_id=group_id
    )


# =============================================================================
# LEGACY TOOLS (still using old architecture)
# =============================================================================

@mcp.tool()
async def create_snippet(
    citation: str,
    key_language: str,
    tags: Optional[List[str]] = None,
    context: Optional[str] = None,
    case_type: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Create legal research snippets (LEGACY VERSION)."""
    await ensure_initialized()
    return await legal_tools.create_snippet(
        db_manager.postgres, db_manager.qdrant, db_manager.graphiti, 
        openai.AsyncOpenAI(api_key=config.api.openai_api_key),
        citation, key_language, tags, context, case_type, group_id
    )


@mcp.tool()
async def unified_legal_search(
    query: str,
    search_type: str = "all",
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Ultimate hybrid search across PostgreSQL + Qdrant + Graphiti (LEGACY VERSION)."""
    await ensure_initialized()
    return await legal_tools.unified_legal_search(
        db_manager.postgres, db_manager.qdrant, db_manager.graphiti,
        openai.AsyncOpenAI(api_key=config.api.openai_api_key),
        query, search_type, group_id
    )


@mcp.tool()
async def get_system_status() -> Dict[str, Any]:
    """Health check for all system components (LEGACY VERSION)."""
    await ensure_initialized()
    return await legal_tools.get_system_status(
        db_manager.postgres, db_manager.qdrant, db_manager.neo4j
    )


# =============================================================================
# RESOURCES (simplified examples)
# =============================================================================

@mcp.resource("suechef://system/status")
async def system_status_resource() -> Dict[str, Any]:
    """Real-time system status and health information."""
    await ensure_initialized()
    return {"status": "healthy", "version": "modular-1.0", "architecture": "layered"}


@mcp.resource("suechef://help/architecture")
def architecture_help_resource() -> str:
    """Information about the new modular architecture."""
    return """
SueChef Modular Architecture:

📁 src/
├── config/         # Centralized configuration
├── core/           # Database managers and clients  
├── services/       # Business logic layer
├── tools/          # MCP interface layer
├── utils/          # Shared utilities
└── models/         # Data models and schemas

🔄 Migration Status:
✅ Events: Fully migrated to EventService
🔄 Snippets: Still using legacy architecture
🔄 Search: Still using legacy architecture
🔄 CourtListener: Still using legacy architecture

🎯 Benefits:
- Modular, testable components
- Clear separation of concerns  
- Easy to extend and maintain
- Type-safe configuration
- Proper dependency injection
"""


# =============================================================================
# SERVER STARTUP
# =============================================================================

if __name__ == "__main__":
    print("🍳 Starting SueChef MCP Server (Modular Architecture)")
    print("📚 Demonstrating new layered architecture with EventService")
    print("🔄 Mixed mode: Events use new architecture, others use legacy")
    
    # Get configuration
    try:
        config = get_config()
        print(f"✅ Configuration loaded (Environment: {config.environment})")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        exit(1)
    
    # Start server
    mcp.run(
        transport="streamable-http",
        host=config.mcp.host,
        port=config.mcp.port,
        path=config.mcp.path,
        log_level=config.mcp.log_level
    )