"""
SueChef MCP Server - Modular Version
A simplified, modular implementation using the new architecture.
"""

import asyncio
from typing import Dict, Any, Optional, List

from fastmcp import FastMCP
import sentry_sdk

sentry_sdk.init(
    dsn="https://fd3d6a0e4c5b7f11180318cac807f590@o4508196072325120.ingest.us.sentry.io/4509425243521024",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    traces_sample_rate=1.0,
)

# Import new modular components
from src.config.settings import get_config
from src.core.database.manager import DatabaseManager
from src.core.database.initializer import initialize_databases
from src.services.legal.event_service import EventService
from src.services.legal.snippet_service import SnippetService
from src.services.external.courtlistener_service import CourtListenerService

# Import legacy tools for features not yet migrated
import legal_tools
import openai


# Initialize FastMCP server
mcp = FastMCP("suechef")

# Global components
config = None
db_manager = None
event_service = None
snippet_service = None
courtlistener_service = None


async def ensure_initialized():
    """Ensure all components are initialized."""
    global config, db_manager, event_service, snippet_service, courtlistener_service
    
    if config is None:
        raise RuntimeError("Services not initialized. This should not happen.")


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


# SNIPPET MANAGEMENT TOOLS (MODULAR VERSION)

@mcp.tool()
async def create_snippet(
    citation: str,
    key_language: str,
    tags: Optional[List[str]] = None,
    context: Optional[str] = None,
    case_type: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Create legal research snippets (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await snippet_service.create_snippet(
        citation=citation,
        key_language=key_language,
        tags=tags,
        context=context,
        case_type=case_type,
        group_id=group_id,
        openai_api_key=config.api.openai_api_key
    )


@mcp.tool()
async def get_snippet(snippet_id: str) -> Dict[str, Any]:
    """Get a single snippet by ID (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await snippet_service.get_snippet(snippet_id)


@mcp.tool()
async def list_snippets(
    limit: int = 50,
    offset: int = 0,
    case_type: Optional[str] = None,
    tags_filter: Optional[List[str]] = None,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """List snippets with optional filtering (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await snippet_service.list_snippets(
        limit=limit,
        offset=offset,
        case_type=case_type,
        tags_filter=tags_filter,
        group_id=group_id
    )


@mcp.tool()
async def update_snippet(
    snippet_id: str,
    citation: Optional[str] = None,
    key_language: Optional[str] = None,
    tags: Optional[List[str]] = None,
    context: Optional[str] = None,
    case_type: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing snippet (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await snippet_service.update_snippet(
        snippet_id=snippet_id,
        citation=citation,
        key_language=key_language,
        tags=tags,
        context=context,
        case_type=case_type,
        openai_api_key=config.api.openai_api_key
    )


@mcp.tool()
async def delete_snippet(snippet_id: str) -> Dict[str, Any]:
    """Delete a snippet from all systems (MODULAR VERSION)."""
    await ensure_initialized()
    
    return await snippet_service.delete_snippet(snippet_id)


# COURTLISTENER INTEGRATION TOOLS (MODULAR VERSION)

@mcp.tool()
async def test_courtlistener_connection() -> Dict[str, Any]:
    """Test CourtListener API connection and authentication (MODULAR VERSION)."""
    await ensure_initialized()
    if courtlistener_service is None:
        return {"status": "error", "message": "CourtListener service not initialized"}
    return await courtlistener_service.test_connection()


@mcp.tool()
async def search_courtlistener_opinions(
    query: str,
    court: Optional[str] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    cited_gt: Optional[int] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Search CourtListener for court opinions matching query (MODULAR VERSION)."""
    await ensure_initialized()
    return await courtlistener_service.search_opinions(
        query=query,
        court=court,
        date_after=date_after,
        date_before=date_before,
        cited_gt=cited_gt,
        limit=limit
    )


@mcp.tool()
async def import_courtlistener_opinion(
    opinion_id: int,
    add_as_snippet: bool = True,
    auto_link_events: bool = True,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Import a CourtListener opinion into your legal research system (MODULAR VERSION)."""
    await ensure_initialized()
    return await courtlistener_service.import_opinion(
        postgres_pool=db_manager.postgres,
        qdrant_client=db_manager.qdrant,
        graphiti_client=db_manager.graphiti,
        openai_client=openai.AsyncOpenAI(api_key=config.api.openai_api_key),
        opinion_id=opinion_id,
        add_as_snippet=add_as_snippet,
        auto_link_events=auto_link_events,
        group_id=group_id
    )


@mcp.tool()
async def search_courtlistener_dockets(
    case_name: Optional[str] = None,
    docket_number: Optional[str] = None,
    court: Optional[str] = None,
    date_filed_after: Optional[str] = None,
    date_filed_before: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Search CourtListener dockets (active cases) (MODULAR VERSION)."""
    await ensure_initialized()
    return await courtlistener_service.search_dockets(
        case_name=case_name,
        docket_number=docket_number,
        court=court,
        date_filed_after=date_filed_after,
        date_filed_before=date_filed_before,
        limit=limit
    )


@mcp.tool()
async def find_citing_opinions(
    citation: str,
    limit: int = 20
) -> Dict[str, Any]:
    """Find all opinions that cite a specific case (MODULAR VERSION)."""
    await ensure_initialized()
    return await courtlistener_service.find_citing_opinions(
        citation=citation,
        limit=limit
    )


@mcp.tool()
async def analyze_courtlistener_precedents(
    topic: str,
    jurisdiction: Optional[str] = None,
    min_citations: int = 5,
    date_range_years: int = 30
) -> Dict[str, Any]:
    """Analyze precedent evolution on a topic using CourtListener data (MODULAR VERSION)."""
    await ensure_initialized()
    return await courtlistener_service.analyze_precedents(
        topic=topic,
        jurisdiction=jurisdiction,
        min_citations=min_citations,
        date_range_years=date_range_years
    )


# =============================================================================
# LEGACY TOOLS (still using old architecture)
# =============================================================================


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
✅ Events: Fully migrated to EventService (3 tools)
✅ Snippets: Fully migrated to SnippetService (5 tools)
🔄 Search: Still using legacy architecture (4 tools)
🔄 CourtListener: Still using legacy architecture (6 tools)
🔄 Analytics: Still using legacy architecture (3 tools)

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

async def initialize_services():
    """Initialize all services at startup"""
    global config, db_manager, event_service, snippet_service, courtlistener_service
    
    try:
        config = get_config()
        print(f"✅ Configuration loaded (Environment: {config.environment})")
        
        # Initialize database manager
        print("🔄 Initializing database connections...")
        db_manager = DatabaseManager(config.database)
        await db_manager.initialize()
        
        # Initialize database schemas
        await initialize_databases(db_manager)
        
        # Initialize services
        print("🔄 Initializing services...")
        event_service = EventService(db_manager)
        snippet_service = SnippetService(db_manager)
        courtlistener_service = CourtListenerService(config)
        
        print(f"✅ All services initialized successfully")
        print(f"   - EventService: {event_service is not None}")
        print(f"   - SnippetService: {snippet_service is not None}")
        print(f"   - CourtListenerService: {courtlistener_service is not None}")
        
    except Exception as e:
        print(f"❌ Service initialization error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    print("🍳 Starting SueChef MCP Server (Modular Architecture)")
    print("📚 Using new layered architecture with EventService + SnippetService")
    print("🔄 Mixed mode: 8 tools migrated, 18 legacy tools transitioning")
    
    # Initialize services synchronously at startup
    import asyncio
    asyncio.run(initialize_services())
    
    # Start server
    mcp.run(
        transport="streamable-http",
        host=config.mcp.host,
        port=config.mcp.port,
        path=config.mcp.path,
        log_level=config.mcp.log_level
    )