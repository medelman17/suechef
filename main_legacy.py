import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastmcp import FastMCP
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
import neo4j
from sqlalchemy import create_engine, text
import numpy as np
import openai

from database_schema import POSTGRES_SCHEMA, QDRANT_COLLECTIONS
import legal_tools
import courtlistener_tools

import sentry_sdk

sentry_sdk.init(
    dsn="https://fd3d6a0e4c5b7f11180318cac807f590@o4508196072325120.ingest.us.sentry.io/4509425243521024",
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    traces_sample_rate=1.0,
)


# Initialize FastMCP server
mcp = FastMCP("suechef")

# Global clients (will be initialized on first use)
postgres_pool = None
qdrant_client = None
graphiti_client = None
neo4j_driver = None
_initialized = False


async def ensure_initialized():
    """Ensure all clients are initialized before tool execution."""
    global _initialized
    if not _initialized:
        await initialize_clients()
        await initialize_databases()
        _initialized = True

# Tool definitions using @mcp.tool() decorator

@mcp.tool()
async def test_array_parameters(
    test_parties: Optional[Any] = None,
    test_tags: Optional[Any] = None
) -> Dict[str, Any]:
    """Test tool for diagnosing array parameter parsing issues."""
    from src.utils.parameter_parsing import parse_string_list
    
    try:
        parties_result = parse_string_list(test_parties)
        tags_result = parse_string_list(test_tags)
        
        return {
            "status": "success",
            "results": {
                "parties": {
                    "input": test_parties,
                    "input_type": str(type(test_parties)),
                    "parsed": parties_result,
                    "parsed_type": str(type(parties_result))
                },
                "tags": {
                    "input": test_tags,
                    "input_type": str(type(test_tags)),
                    "parsed": tags_result,
                    "parsed_type": str(type(tags_result))
                }
            },
            "message": "Array parameter parsing test completed successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Array parsing test failed: {str(e)}",
            "debug_info": {
                "test_parties": str(test_parties),
                "test_tags": str(test_tags)
            }
        }

@mcp.tool()
async def add_event(
    date: str,
    description: str,
    parties: Optional[Any] = None,  # Accept Any type for flexible parsing
    document_source: Optional[str] = None,
    excerpts: Optional[str] = None,
    tags: Optional[Any] = None,     # Accept Any type for flexible parsing
    significance: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Add chronology events with automatic vector and knowledge graph storage (ROBUST VERSION)."""
    await ensure_initialized()
    
    # Import parameter parsing utilities
    from src.utils.parameter_parsing import normalize_event_parameters
    
    try:
        # Normalize parameters to handle different input formats
        params = normalize_event_parameters(
            date=date,
            description=description,
            parties=parties,
            document_source=document_source,
            excerpts=excerpts,
            tags=tags,
            significance=significance,
            group_id=group_id
        )
        
        # Call the original function with normalized parameters
        return await legal_tools.add_event(
            postgres_pool, qdrant_client, graphiti_client, 
            openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
            params["date"], params["description"], params["parties"], 
            params["document_source"], params["excerpts"], params["tags"], 
            params["significance"], params["group_id"]
        )
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Parameter parsing or execution error: {str(e)}",
            "error_type": "parameter_parsing_error",
            "debug_info": {
                "received_parties": str(parties),
                "received_tags": str(tags),
                "parties_type": str(type(parties)),
                "tags_type": str(type(tags))
            }
        }

@mcp.tool()
async def create_snippet(
    citation: str,
    key_language: str,
    tags: Optional[List[str]] = None,
    context: Optional[str] = None,
    case_type: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Create legal research snippets (case law, precedents, statutes)."""
    return await legal_tools.create_snippet(
        postgres_pool, qdrant_client, graphiti_client, openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
        citation, key_language, tags, context, case_type, group_id
    )

@mcp.tool()
async def unified_legal_search(
    query: str,
    search_type: str = "all",
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Ultimate hybrid search across PostgreSQL + Qdrant + Graphiti."""
    return await legal_tools.unified_legal_search(
        postgres_pool, qdrant_client, graphiti_client, openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
        query, search_type, group_id
    )

@mcp.tool()
async def postgres_full_text_search(
    query: str,
    search_type: str = "all"
) -> Dict[str, Any]:
    """Advanced PostgreSQL full-text search with relevance ranking."""
    return await legal_tools.postgres_full_text_search(postgres_pool, query, search_type)

@mcp.tool()
async def postgres_advanced_query(
    sql_condition: str,
    target_table: str,
    parameters: Optional[Dict] = None
) -> Dict[str, Any]:
    """Execute complex PostgreSQL queries with JSONB operations."""
    return await legal_tools.postgres_advanced_query(postgres_pool, sql_condition, target_table, parameters)

@mcp.tool()
async def ingest_legal_document(
    document_text: str,
    title: str,
    date: Optional[str] = None,
    document_type: Optional[str] = None
) -> Dict[str, Any]:
    """Feed entire legal documents to Graphiti for automatic processing."""
    return await legal_tools.ingest_legal_document(graphiti_client, document_text, title, date, document_type)

@mcp.tool()
async def temporal_legal_query(
    question: str,
    time_focus: Optional[str] = None,
    entity_focus: Optional[str] = None
) -> Dict[str, Any]:
    """Ask temporal questions about legal knowledge evolution."""
    return await legal_tools.temporal_legal_query(graphiti_client, question, time_focus, entity_focus)

@mcp.tool()
async def create_manual_link(
    event_id: str,
    snippet_id: str,
    relationship_type: str,
    confidence: Optional[float] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Create explicit relationships between events and legal precedents."""
    return await legal_tools.create_manual_link(
        postgres_pool, event_id, snippet_id, relationship_type, confidence, notes
    )

@mcp.tool()
async def get_legal_analytics() -> Dict[str, Any]:
    """Comprehensive legal research analytics using PostgreSQL power."""
    return await legal_tools.get_legal_analytics(postgres_pool)

@mcp.tool()
async def get_system_status() -> Dict[str, Any]:
    """Health check for all system components."""
    await ensure_initialized()
    return await legal_tools.get_system_status(postgres_pool, qdrant_client, neo4j_driver)

# READ operations
@mcp.tool()
async def get_event(event_id: str) -> Dict[str, Any]:
    """Get a single event by ID."""
    return await legal_tools.get_event(postgres_pool, event_id)

@mcp.tool()
async def get_snippet(snippet_id: str) -> Dict[str, Any]:
    """Get a single snippet by ID."""
    return await legal_tools.get_snippet(postgres_pool, snippet_id)

@mcp.tool()
async def list_events(
    limit: int = 50,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    parties_filter: Optional[List[str]] = None,
    tags_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """List events with optional filtering by date, parties, or tags."""
    return await legal_tools.list_events(
        postgres_pool, limit, offset, date_from, date_to, parties_filter, tags_filter
    )

@mcp.tool()
async def list_snippets(
    limit: int = 50,
    offset: int = 0,
    case_type: Optional[str] = None,
    tags_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """List snippets with optional filtering by case type or tags."""
    return await legal_tools.list_snippets(postgres_pool, limit, offset, case_type, tags_filter)

# UPDATE operations
@mcp.tool()
async def update_event(
    event_id: str,
    date: Optional[str] = None,
    description: Optional[str] = None,
    parties: Optional[List[str]] = None,
    document_source: Optional[str] = None,
    excerpts: Optional[str] = None,
    tags: Optional[List[str]] = None,
    significance: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing event (only specified fields will be updated)."""
    return await legal_tools.update_event(
        postgres_pool, qdrant_client, graphiti_client, openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
        event_id, date, description, parties, document_source, excerpts, tags, significance
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
    """Update an existing snippet (only specified fields will be updated)."""
    return await legal_tools.update_snippet(
        postgres_pool, qdrant_client, graphiti_client, openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
        snippet_id, citation, key_language, tags, context, case_type
    )

# DELETE operations
@mcp.tool()
async def delete_event(event_id: str) -> Dict[str, Any]:
    """Delete an event from all systems."""
    return await legal_tools.delete_event(postgres_pool, qdrant_client, event_id)

@mcp.tool()
async def delete_snippet(snippet_id: str) -> Dict[str, Any]:
    """Delete a snippet from all systems."""
    return await legal_tools.delete_snippet(postgres_pool, qdrant_client, snippet_id)

# CourtListener integration tools
@mcp.tool()
async def search_courtlistener_opinions(
    query: str,
    court: Optional[str] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    cited_gt: Optional[int] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Search CourtListener for court opinions matching query."""
    return await courtlistener_tools.search_courtlistener_opinions(
        query, court, date_after, date_before, cited_gt, limit
    )

@mcp.tool()
async def import_courtlistener_opinion(
    opinion_id: int,
    add_as_snippet: bool = True,
    auto_link_events: bool = True
) -> Dict[str, Any]:
    """Import a CourtListener opinion into your legal research system."""
    return await courtlistener_tools.import_courtlistener_opinion(
        postgres_pool, qdrant_client, graphiti_client, openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
        opinion_id, add_as_snippet, auto_link_events
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
    """Search CourtListener dockets (active cases) for procedural history and party information."""
    return await courtlistener_tools.search_courtlistener_dockets(
        case_name, docket_number, court, date_filed_after, date_filed_before, limit
    )

@mcp.tool()
async def find_citing_opinions(citation: str, limit: int = 20) -> Dict[str, Any]:
    """Find all opinions that cite a specific case."""
    return await courtlistener_tools.find_citing_opinions(citation, limit)

@mcp.tool()
async def analyze_courtlistener_precedents(
    topic: str,
    jurisdiction: Optional[str] = None,
    min_citations: int = 5,
    date_range_years: int = 30
) -> Dict[str, Any]:
    """Analyze precedent evolution on a topic using CourtListener data."""
    return await courtlistener_tools.analyze_courtlistener_precedents(
        topic, jurisdiction, min_citations, date_range_years
    )

@mcp.tool()
async def test_courtlistener_connection() -> Dict[str, Any]:
    """Test CourtListener API connection and authentication."""
    return await courtlistener_tools.test_courtlistener_connection()

# Community Detection operations
@mcp.tool()
async def build_legal_communities(group_id: Optional[str] = None) -> Dict[str, Any]:
    """Build communities in the knowledge graph to identify related legal concepts."""
    return await legal_tools.build_legal_communities(graphiti_client, group_id)

@mcp.tool()
async def search_legal_communities(
    query: str,
    group_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """Search for communities related to a legal query."""
    return await legal_tools.search_legal_communities(graphiti_client, query, group_id, limit)

@mcp.tool()
async def enhanced_legal_search(
    query: str,
    search_focus: str = "hybrid",
    group_id: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Enhanced search using SearchConfig for configurable node/edge/community retrieval."""
    return await legal_tools.enhanced_legal_search(
        postgres_pool, qdrant_client, graphiti_client, openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", "")),
        query, search_focus, group_id, limit
    )


# RESOURCES - Data access points for legal information

@mcp.resource("suechef://system/status")
async def system_status_resource() -> Dict[str, Any]:
    """Real-time system status and health information."""
    return await get_system_status()

@mcp.resource("suechef://analytics/legal")
async def legal_analytics_resource() -> Dict[str, Any]:
    """Current legal research analytics and statistics."""
    return await get_legal_analytics()

@mcp.resource("suechef://events/recent")
async def recent_events_resource() -> Dict[str, Any]:
    """Recently added chronology events."""
    return await list_events(limit=10, offset=0)

@mcp.resource("suechef://snippets/recent")
async def recent_snippets_resource() -> Dict[str, Any]:
    """Recently added legal snippets."""
    return await list_snippets(limit=10, offset=0)

@mcp.resource("suechef://search/trending")
async def trending_search_resource() -> str:
    """Information about trending legal search patterns."""
    return "Recent trending searches: landlord liability, water damage, premises liability, duty to repair"

@mcp.resource("suechef://help/tools")
def tools_help_resource() -> str:
    """Complete list of available SueChef tools and their descriptions."""
    return """
SueChef Legal Research Tools (26 tools available):

📅 EVENT MANAGEMENT:
• add_event - Add chronology events with automatic vector/knowledge graph storage
• get_event - Retrieve single event by ID
• list_events - List events with date/party/tag filtering
• update_event - Update existing events (partial updates supported)
• delete_event - Remove events from all systems

📋 SNIPPET MANAGEMENT:
• create_snippet - Create legal research snippets (cases, precedents, statutes)
• get_snippet - Retrieve single snippet by ID
• list_snippets - List snippets with case type/tag filtering
• update_snippet - Update existing snippets (partial updates supported)
• delete_snippet - Remove snippets from all systems

🔍 SEARCH & DISCOVERY:
• unified_legal_search - Hybrid search across PostgreSQL + Qdrant + Graphiti
• postgres_full_text_search - Advanced PostgreSQL full-text search
• postgres_advanced_query - Complex JSONB queries
• enhanced_legal_search - Configurable node/edge/community search

📄 DOCUMENT PROCESSING:
• ingest_legal_document - Process full documents for entity extraction

🕐 TEMPORAL INTELLIGENCE:
• temporal_legal_query - Ask temporal questions about legal knowledge evolution

🔗 RELATIONSHIP MANAGEMENT:
• create_manual_link - Link events to legal precedents

📊 ANALYTICS & INSIGHTS:
• get_legal_analytics - Comprehensive legal research analytics
• get_system_status - Health check for all system components

⚖️ COURTLISTENER INTEGRATION:
• search_courtlistener_opinions - Search millions of court opinions
• import_courtlistener_opinion - Import opinions as snippets
• search_courtlistener_dockets - Find active cases and procedural history
• find_citing_opinions - Discover cases citing specific precedents
• analyze_courtlistener_precedents - Analyze precedent evolution

🧠 KNOWLEDGE GRAPH FEATURES:
• build_legal_communities - Identify legal concept clusters
• search_legal_communities - Search within community structures

All tools support group-based namespacing for multi-client data isolation.
"""


# PROMPTS - Reusable templates for legal research workflows

@mcp.prompt()
def legal_case_analysis(case_name: str, jurisdiction: str = "federal") -> str:
    """Generate a comprehensive legal case analysis prompt."""
    return f"""
Analyze the legal case "{case_name}" in {jurisdiction} jurisdiction. Please provide:

1. **Case Summary**: Brief overview of the facts and procedural posture
2. **Legal Issues**: Key legal questions presented
3. **Holdings**: Primary legal holdings and rulings
4. **Precedential Value**: Binding vs. persuasive authority analysis
5. **Related Cases**: Similar cases and distinguishable precedents
6. **Practice Implications**: How this case affects legal practice

Use SueChef tools to search for related precedents and analyze the case within the broader legal landscape.
"""

@mcp.prompt()
def legal_research_strategy(research_topic: str, client_situation: str = "general inquiry") -> str:
    """Create a systematic legal research strategy prompt."""
    return f"""
Develop a comprehensive legal research strategy for: {research_topic}

**Client Situation**: {client_situation}

**Research Plan**:
1. **Primary Sources**: Constitutional provisions, statutes, regulations
2. **Secondary Sources**: Legal encyclopedias, law reviews, practice guides
3. **Case Law Research**: Binding and persuasive precedents
4. **Current Developments**: Recent cases, legislative changes
5. **Jurisdiction Analysis**: Federal vs. state law considerations

**SueChef Research Steps**:
1. Use `unified_legal_search` to find existing case law and precedents
2. Use `search_courtlistener_opinions` for comprehensive case discovery
3. Use `temporal_legal_query` to understand legal evolution over time
4. Use `build_legal_communities` to identify related legal concepts
5. Create timeline with `add_event` for key legal developments

Please execute this research plan systematically and provide findings.
"""

@mcp.prompt()
def contract_review_checklist(contract_type: str = "general agreement") -> str:
    """Generate a contract review checklist prompt."""
    return f"""
Perform a comprehensive review of this {contract_type} using the following checklist:

**ESSENTIAL ELEMENTS**:
□ Parties clearly identified with capacity
□ Consideration adequately described
□ Terms and conditions clearly stated
□ Performance obligations specified
□ Duration and termination provisions

**RISK ANALYSIS**:
□ Liability and indemnification clauses
□ Force majeure provisions
□ Dispute resolution mechanisms
□ Governing law and jurisdiction
□ Intellectual property rights

**COMPLIANCE CHECK**:
□ Applicable statutes and regulations
□ Industry-specific requirements
□ Consumer protection laws (if applicable)
□ Data privacy compliance (GDPR, CCPA, etc.)

**NEGOTIATION POINTS**:
□ Unfavorable terms for client
□ Missing protective clauses
□ Ambiguous language requiring clarification
□ Standard vs. negotiable provisions

Use SueChef to research relevant case law and regulatory requirements for each provision.
"""

@mcp.prompt()
def litigation_timeline_builder(case_name: str, filing_date: str) -> str:
    """Create a litigation timeline and case management prompt."""
    return f"""
Build a comprehensive litigation timeline for {case_name} (filed: {filing_date}):

**CASE SETUP**:
1. Use `add_event` to create initial filing entry
2. Research similar cases with `search_courtlistener_dockets`
3. Identify key precedents with `find_citing_opinions`

**DISCOVERY PHASE**:
□ Document production deadlines
□ Deposition schedules
□ Expert witness disclosures
□ Motion practice deadlines

**PROCEDURAL MILESTONES**:
□ Answer/responsive pleading due
□ Motion to dismiss deadline
□ Summary judgment motions
□ Pre-trial conference
□ Trial date

**RESEARCH TASKS**:
□ Analyze controlling precedents
□ Review similar case outcomes
□ Track recent legal developments
□ Monitor appeals in related cases

Use SueChef's timeline management to track all deadlines and create automated research updates for case developments.
"""

@mcp.prompt()
def regulatory_compliance_audit(industry: str, jurisdiction: str = "federal") -> str:
    """Generate a regulatory compliance audit prompt."""
    return f"""
Conduct a regulatory compliance audit for {industry} sector in {jurisdiction} jurisdiction:

**REGULATORY FRAMEWORK**:
1. Primary federal regulations and agencies
2. State-specific requirements
3. Industry standards and best practices
4. Recent regulatory changes and proposals

**COMPLIANCE AREAS**:
□ Licensing and permits
□ Environmental regulations
□ Labor and employment law
□ Consumer protection
□ Data privacy and security
□ Financial regulations (if applicable)
□ Health and safety standards

**RESEARCH METHODOLOGY**:
1. Use `postgres_advanced_query` to search regulatory databases
2. Use `temporal_legal_query` to track regulatory evolution
3. Use `search_courtlistener_opinions` for enforcement cases
4. Use `analyze_courtlistener_precedents` for compliance trends

**DELIVERABLES**:
□ Compliance gap analysis
□ Risk assessment matrix
□ Recommended action items
□ Implementation timeline
□ Ongoing monitoring plan

Provide specific recommendations based on current regulatory landscape and recent enforcement actions.
"""

@mcp.prompt()
def precedent_evolution_analysis(legal_doctrine: str, time_period: str = "30 years") -> str:
    """Analyze how a legal doctrine has evolved over time."""
    return f"""
Analyze the evolution of {legal_doctrine} over the past {time_period}:

**HISTORICAL DEVELOPMENT**:
1. Foundational cases and original doctrine
2. Key evolutionary moments and turning points
3. Current state of the law
4. Emerging trends and future direction

**RESEARCH APPROACH**:
1. Use `analyze_courtlistener_precedents` for comprehensive case analysis
2. Use `temporal_legal_query` for timeline-based insights
3. Use `enhanced_legal_search` with communities focus for related concepts
4. Use `build_legal_communities` to map doctrinal relationships

**ANALYSIS FRAMEWORK**:
□ Circuit splits and conflicting interpretations
□ Supreme Court guidance and clarity
□ Scholarly commentary and criticism
□ Practical implications for practitioners
□ Prediction of future developments

**JURISDICTION COMPARISON**:
□ Federal court trends
□ State court variations
□ International perspectives (if relevant)
□ Model code and uniform law influences

Provide comprehensive analysis with supporting case citations and practical implications for current legal practice.
"""


async def initialize_clients():
    """Initialize all database and service clients with enhanced connection management."""
    global postgres_pool, qdrant_client, graphiti_client, neo4j_driver
    
    try:
        # Initialize PostgreSQL with connection pool settings
        postgres_pool = await asyncpg.create_pool(
            os.getenv("POSTGRES_URL", "postgresql://localhost/legal_research"),
            min_size=2,           # Minimum connections
            max_size=10,          # Maximum connections  
            max_queries=50000,    # Max queries per connection
            max_inactive_connection_lifetime=300,  # 5 minutes
            command_timeout=30    # 30 second timeout
        )
        
        # Test PostgreSQL connection
        async with postgres_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        print("✅ PostgreSQL connection established")
        
        # Initialize Qdrant
        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333")
        )
        # Test Qdrant connection
        qdrant_client.get_collections()
        print("✅ Qdrant connection established")
        
        # Initialize Neo4j with connection pool settings
        neo4j_driver = neo4j.GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
            max_connection_lifetime=30 * 60,  # 30 minutes
            max_connection_pool_size=50,
            connection_acquisition_timeout=30  # 30 seconds
        )
        
        # Test Neo4j connection
        with neo4j_driver.session() as session:
            session.run("RETURN 1")
        print("✅ Neo4j connection established")
        
        # Initialize Graphiti
        graphiti_client = Graphiti(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password")
        )
        
        # CRITICAL: Build indices and constraints after initialization
        await graphiti_client.build_indices_and_constraints()
        print("✅ Graphiti initialized with indices and constraints")
        
        print("🎉 All database connections initialized successfully")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise


async def initialize_databases():
    """Initialize database schemas and collections."""
    global postgres_pool, qdrant_client
    
    # Initialize PostgreSQL schema
    async with postgres_pool.acquire() as conn:
        await conn.execute(POSTGRES_SCHEMA)
    
    # Initialize Qdrant collections
    for collection_name, config in QDRANT_COLLECTIONS.items():
        try:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=config["size"],
                    distance=Distance[config["distance"].upper()]
                )
            )
        except Exception as e:
            # Collection might already exist
            pass


async def startup():
    """Initialize everything on server startup."""
    await initialize_clients()
    await initialize_databases()


if __name__ == "__main__":
    # Run the MCP server with Streaming HTTP transport
    import os
    
    host = os.getenv("MCP_HOST", "0.0.0.0")  # Bind to all interfaces in container
    port = int(os.getenv("MCP_PORT", "8000"))
    path = os.getenv("MCP_PATH", "/mcp")
    log_level = os.getenv("MCP_LOG_LEVEL", "info")
    
    print(f"🍳 Starting SueChef MCP Server on http://{host}:{port}{path}")
    print(f"📚 Legal research tools available: 26 total tools")
    
    # FastMCP will handle async initialization internally
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        path=path,
        log_level=log_level
    )