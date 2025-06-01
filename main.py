import asyncio
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastmcp import FastMCP
from fastmcp.fastmcp.types import Tool
import asyncpg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode, EpisodeNode
from graphiti_core.edges import EntityRelation, EpisodicEdge
import neo4j
from sqlalchemy import create_engine, text
import numpy as np
import openai

from database_schema import POSTGRES_SCHEMA, QDRANT_COLLECTIONS
import legal_tools
import courtlistener_tools

# Initialize FastMCP server
mcp = FastMCP("suechef")

# Global clients (will be initialized on startup)
postgres_pool = None
qdrant_client = None
graphiti_client = None
neo4j_driver = None


@mcp.server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available legal research tools."""
    return [
        Tool(
            name="add_event",
            description="Add chronology events with automatic vector and knowledge graph storage",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Event date (YYYY-MM-DD)"},
                    "description": {"type": "string", "description": "Event description"},
                    "parties": {"type": "array", "items": {"type": "string"}, "description": "Parties involved"},
                    "document_source": {"type": "string", "description": "Source document"},
                    "excerpts": {"type": "string", "description": "Relevant excerpts"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization"},
                    "significance": {"type": "string", "description": "Legal significance"}
                },
                "required": ["date", "description"]
            }
        ),
        Tool(
            name="create_snippet",
            description="Create legal research snippets (case law, precedents, statutes)",
            inputSchema={
                "type": "object",
                "properties": {
                    "citation": {"type": "string", "description": "Legal citation"},
                    "key_language": {"type": "string", "description": "Key legal language"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
                    "context": {"type": "string", "description": "Context"},
                    "case_type": {"type": "string", "description": "Type of case"}
                },
                "required": ["citation", "key_language"]
            }
        ),
        Tool(
            name="unified_legal_search",
            description="Ultimate hybrid search across PostgreSQL + Qdrant + Graphiti",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "search_type": {
                        "type": "string",
                        "enum": ["vector", "postgres", "knowledge_graph", "all"],
                        "description": "Type of search to perform",
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="postgres_full_text_search",
            description="Advanced PostgreSQL full-text search with relevance ranking",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "search_type": {
                        "type": "string",
                        "enum": ["events", "snippets", "all"],
                        "description": "What to search",
                        "default": "all"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="postgres_advanced_query",
            description="Execute complex PostgreSQL queries with JSONB operations",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql_condition": {"type": "string", "description": "SQL WHERE clause condition"},
                    "target_table": {
                        "type": "string",
                        "enum": ["events", "snippets"],
                        "description": "Table to query"
                    },
                    "parameters": {"type": "object", "description": "Query parameters"}
                },
                "required": ["sql_condition", "target_table"]
            }
        ),
        Tool(
            name="ingest_legal_document",
            description="Feed entire legal documents to Graphiti for automatic processing",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_text": {"type": "string", "description": "Full document text"},
                    "title": {"type": "string", "description": "Document title"},
                    "date": {"type": "string", "description": "Document date"},
                    "document_type": {"type": "string", "description": "Type of document"}
                },
                "required": ["document_text", "title"]
            }
        ),
        Tool(
            name="temporal_legal_query",
            description="Ask temporal questions about legal knowledge evolution",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Temporal question"},
                    "time_focus": {"type": "string", "description": "Time period of interest"},
                    "entity_focus": {"type": "string", "description": "Specific entity to focus on"}
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="create_manual_link",
            description="Create explicit relationships between events and legal precedents",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID"},
                    "snippet_id": {"type": "string", "description": "Snippet ID"},
                    "relationship_type": {"type": "string", "description": "Type of relationship"},
                    "confidence": {"type": "number", "description": "Confidence score (0-1)"},
                    "notes": {"type": "string", "description": "Additional notes"}
                },
                "required": ["event_id", "snippet_id", "relationship_type"]
            }
        ),
        Tool(
            name="get_legal_analytics",
            description="Comprehensive legal research analytics using PostgreSQL power",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_system_status",
            description="Health check for all system components",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # READ operations
        Tool(
            name="get_event",
            description="Get a single event by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID (UUID)"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="get_snippet",
            description="Get a single snippet by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "snippet_id": {"type": "string", "description": "Snippet ID (UUID)"}
                },
                "required": ["snippet_id"]
            }
        ),
        Tool(
            name="list_events",
            description="List events with optional filtering by date, parties, or tags",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 50},
                    "offset": {"type": "integer", "description": "Offset for pagination", "default": 0},
                    "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                    "parties_filter": {"type": "array", "items": {"type": "string"}, "description": "Filter by parties"},
                    "tags_filter": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"}
                }
            }
        ),
        Tool(
            name="list_snippets",
            description="List snippets with optional filtering by case type or tags",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 50},
                    "offset": {"type": "integer", "description": "Offset for pagination", "default": 0},
                    "case_type": {"type": "string", "description": "Filter by case type"},
                    "tags_filter": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags"}
                }
            }
        ),
        # UPDATE operations
        Tool(
            name="update_event",
            description="Update an existing event (only specified fields will be updated)",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to update"},
                    "date": {"type": "string", "description": "Event date (YYYY-MM-DD)"},
                    "description": {"type": "string", "description": "Event description"},
                    "parties": {"type": "array", "items": {"type": "string"}, "description": "Parties involved"},
                    "document_source": {"type": "string", "description": "Source document"},
                    "excerpts": {"type": "string", "description": "Relevant excerpts"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
                    "significance": {"type": "string", "description": "Legal significance"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="update_snippet",
            description="Update an existing snippet (only specified fields will be updated)",
            inputSchema={
                "type": "object",
                "properties": {
                    "snippet_id": {"type": "string", "description": "Snippet ID to update"},
                    "citation": {"type": "string", "description": "Legal citation"},
                    "key_language": {"type": "string", "description": "Key legal language"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
                    "context": {"type": "string", "description": "Context"},
                    "case_type": {"type": "string", "description": "Type of case"}
                },
                "required": ["snippet_id"]
            }
        ),
        # DELETE operations
        Tool(
            name="delete_event",
            description="Delete an event from all systems",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Event ID to delete"}
                },
                "required": ["event_id"]
            }
        ),
        Tool(
            name="delete_snippet",
            description="Delete a snippet from all systems",
            inputSchema={
                "type": "object",
                "properties": {
                    "snippet_id": {"type": "string", "description": "Snippet ID to delete"}
                },
                "required": ["snippet_id"]
            }
        ),
        # CourtListener integration tools
        Tool(
            name="search_courtlistener_opinions",
            description="Search CourtListener for court opinions matching query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search terms (e.g., 'landlord tenant water damage')"},
                    "court": {"type": "string", "description": "Court abbreviation (e.g., 'scotus', 'ca9')"},
                    "date_after": {"type": "string", "description": "Filter opinions after this date (YYYY-MM-DD)"},
                    "date_before": {"type": "string", "description": "Filter opinions before this date"},
                    "cited_gt": {"type": "integer", "description": "Minimum number of times opinion has been cited"},
                    "limit": {"type": "integer", "description": "Maximum results to return", "default": 20}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="import_courtlistener_opinion",
            description="Import a CourtListener opinion into your legal research system",
            inputSchema={
                "type": "object",
                "properties": {
                    "opinion_id": {"type": "integer", "description": "CourtListener opinion ID"},
                    "add_as_snippet": {"type": "boolean", "description": "Create a snippet in your local system", "default": true},
                    "auto_link_events": {"type": "boolean", "description": "Attempt to link with existing chronology events", "default": true}
                },
                "required": ["opinion_id"]
            }
        ),
        Tool(
            name="search_courtlistener_dockets",
            description="Search CourtListener dockets (active cases) for procedural history and party information",
            inputSchema={
                "type": "object",
                "properties": {
                    "case_name": {"type": "string", "description": "Case name to search for"},
                    "docket_number": {"type": "string", "description": "Docket number"},
                    "court": {"type": "string", "description": "Court abbreviation"},
                    "date_filed_after": {"type": "string", "description": "Cases filed after this date (YYYY-MM-DD)"},
                    "date_filed_before": {"type": "string", "description": "Cases filed before this date"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 20}
                }
            }
        ),
        Tool(
            name="find_citing_opinions",
            description="Find all opinions that cite a specific case",
            inputSchema={
                "type": "object",
                "properties": {
                    "citation": {"type": "string", "description": "Citation to search for (e.g., '123 F.3d 456')"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 20}
                },
                "required": ["citation"]
            }
        ),
        Tool(
            name="analyze_courtlistener_precedents",
            description="Analyze precedent evolution on a topic using CourtListener data",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Legal topic to analyze"},
                    "jurisdiction": {"type": "string", "description": "Court jurisdiction (e.g., 'ca9')"},
                    "min_citations": {"type": "integer", "description": "Minimum citation count", "default": 5},
                    "date_range_years": {"type": "integer", "description": "Years of history to analyze", "default": 30}
                },
                "required": ["topic"]
            }
        )
    ]


@mcp.server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Route tool calls to appropriate handlers."""
    global postgres_pool, qdrant_client, graphiti_client, neo4j_driver
    
    # Ensure clients are initialized
    if not postgres_pool:
        await initialize_clients()
    
    # Initialize OpenAI client
    openai_client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    
    try:
        if name == "add_event":
            result = await legal_tools.add_event(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                **arguments
            )
        elif name == "create_snippet":
            result = await legal_tools.create_snippet(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                **arguments
            )
        elif name == "unified_legal_search":
            result = await legal_tools.unified_legal_search(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                **arguments
            )
        elif name == "postgres_full_text_search":
            result = await legal_tools.postgres_full_text_search(
                postgres_pool, **arguments
            )
        elif name == "postgres_advanced_query":
            result = await legal_tools.postgres_advanced_query(
                postgres_pool, **arguments
            )
        elif name == "ingest_legal_document":
            result = await legal_tools.ingest_legal_document(
                graphiti_client, **arguments
            )
        elif name == "temporal_legal_query":
            result = await legal_tools.temporal_legal_query(
                graphiti_client, **arguments
            )
        elif name == "create_manual_link":
            result = await legal_tools.create_manual_link(
                postgres_pool, **arguments
            )
        elif name == "get_legal_analytics":
            result = await legal_tools.get_legal_analytics(postgres_pool)
        elif name == "get_system_status":
            result = await legal_tools.get_system_status(
                postgres_pool, qdrant_client, neo4j_driver
            )
        # READ operations
        elif name == "get_event":
            result = await legal_tools.get_event(postgres_pool, **arguments)
        elif name == "get_snippet":
            result = await legal_tools.get_snippet(postgres_pool, **arguments)
        elif name == "list_events":
            result = await legal_tools.list_events(postgres_pool, **arguments)
        elif name == "list_snippets":
            result = await legal_tools.list_snippets(postgres_pool, **arguments)
        # UPDATE operations
        elif name == "update_event":
            result = await legal_tools.update_event(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                **arguments
            )
        elif name == "update_snippet":
            result = await legal_tools.update_snippet(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                **arguments
            )
        # DELETE operations
        elif name == "delete_event":
            result = await legal_tools.delete_event(
                postgres_pool, qdrant_client, **arguments
            )
        elif name == "delete_snippet":
            result = await legal_tools.delete_snippet(
                postgres_pool, qdrant_client, **arguments
            )
        # CourtListener operations
        elif name == "search_courtlistener_opinions":
            result = await courtlistener_tools.search_courtlistener_opinions(**arguments)
        elif name == "import_courtlistener_opinion":
            result = await courtlistener_tools.import_courtlistener_opinion(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                **arguments
            )
        elif name == "search_courtlistener_dockets":
            result = await courtlistener_tools.search_courtlistener_dockets(**arguments)
        elif name == "find_citing_opinions":
            result = await courtlistener_tools.find_citing_opinions(**arguments)
        elif name == "analyze_courtlistener_precedents":
            result = await courtlistener_tools.analyze_courtlistener_precedents(**arguments)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
        
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": name})


async def initialize_clients():
    """Initialize all database and service clients."""
    global postgres_pool, qdrant_client, graphiti_client, neo4j_driver
    
    # Initialize PostgreSQL
    postgres_pool = await asyncpg.create_pool(
        os.getenv("POSTGRES_URL", "postgresql://localhost/legal_research")
    )
    
    # Initialize Qdrant
    qdrant_client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    
    # Initialize Neo4j
    neo4j_driver = neo4j.GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))
    )
    
    # Initialize Graphiti
    graphiti_client = Graphiti(
        neo4j_driver=neo4j_driver,
        openai_api_key=os.getenv("OPENAI_API_KEY", "")
    )


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


@mcp.server.startup()
async def startup():
    """Initialize everything on server startup."""
    await initialize_clients()
    await initialize_databases()


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
