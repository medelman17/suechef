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

# Initialize FastMCP server
mcp = FastMCP("unified-legal-mcp")

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
