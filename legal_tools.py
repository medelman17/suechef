"""Implementation of legal research tools."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import asyncpg
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
import openai
from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode, EpisodeNode
from graphiti_core.edges import EntityRelation, EpisodicEdge
import numpy as np


async def get_embedding(text: str, openai_client) -> List[float]:
    """Get OpenAI embedding for text."""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


async def add_event(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    graphiti_client: Graphiti,
    openai_client,
    date: str,
    description: str,
    parties: List[str] = None,
    document_source: str = None,
    excerpts: str = None,
    tags: List[str] = None,
    significance: str = None
) -> Dict[str, Any]:
    """Add a chronology event with automatic vector and knowledge graph storage."""
    
    # Insert into PostgreSQL
    async with postgres_pool.acquire() as conn:
        event_id = await conn.fetchval(
            """
            INSERT INTO events (date, description, parties, document_source, excerpts, tags, significance)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            datetime.strptime(date, "%Y-%m-%d").date(),
            description,
            json.dumps(parties or []),
            document_source,
            excerpts,
            json.dumps(tags or []),
            significance
        )
    
    # Create embedding and store in Qdrant
    full_text = f"{description} {excerpts or ''} {significance or ''}"
    embedding = await get_embedding(full_text, openai_client)
    
    qdrant_client.upsert(
        collection_name="legal_events",
        points=[
            PointStruct(
                id=str(event_id),
                vector=embedding,
                payload={
                    "date": date,
                    "description": description,
                    "parties": parties or [],
                    "tags": tags or [],
                    "type": "event"
                }
            )
        ]
    )
    
    # Add to Graphiti knowledge graph
    episode_content = f"On {date}: {description}"
    if excerpts:
        episode_content += f"\\nExcerpts: {excerpts}"
    
    await graphiti_client.add_episode(
        content=episode_content,
        source=document_source or "Legal Timeline",
        id=str(event_id),
        timestamp=datetime.strptime(date, "%Y-%m-%d")
    )
    
    return {
        "event_id": str(event_id),
        "status": "success",
        "message": "Event added to all systems successfully"
    }


async def create_snippet(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    graphiti_client: Graphiti,
    openai_client,
    citation: str,
    key_language: str,
    tags: List[str] = None,
    context: str = None,
    case_type: str = None
) -> Dict[str, Any]:
    """Create a legal research snippet with automatic entity extraction."""
    
    # Insert into PostgreSQL
    async with postgres_pool.acquire() as conn:
        snippet_id = await conn.fetchval(
            """
            INSERT INTO snippets (citation, key_language, tags, context, case_type)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            citation,
            key_language,
            json.dumps(tags or []),
            context,
            case_type
        )
    
    # Create embedding and store in Qdrant
    full_text = f"{citation} {key_language} {context or ''}"
    embedding = await get_embedding(full_text, openai_client)
    
    qdrant_client.upsert(
        collection_name="legal_snippets",
        points=[
            PointStruct(
                id=str(snippet_id),
                vector=embedding,
                payload={
                    "citation": citation,
                    "key_language": key_language[:200],  # Truncate for payload
                    "tags": tags or [],
                    "case_type": case_type,
                    "type": "snippet"
                }
            )
        ]
    )
    
    # Add to Graphiti
    content = f"Legal Precedent: {citation}\\n{key_language}"
    if context:
        content += f"\\nContext: {context}"
    
    await graphiti_client.add_episode(
        content=content,
        source=citation,
        id=str(snippet_id),
        timestamp=datetime.now()
    )
    
    return {
        "snippet_id": str(snippet_id),
        "status": "success",
        "message": "Snippet added to all systems successfully"
    }


async def unified_legal_search(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    graphiti_client: Graphiti,
    openai_client,
    query: str,
    search_type: str = "all"
) -> Dict[str, Any]:
    """Perform hybrid search across all systems."""
    results = {}
    
    # PostgreSQL full-text search
    if search_type in ["postgres", "all"]:
        async with postgres_pool.acquire() as conn:
            events = await conn.fetch(
                """
                SELECT id, date, description, parties, tags, 
                       ts_rank(search_vector, plainto_tsquery('english', $1)) as rank
                FROM events
                WHERE search_vector @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT 10
                """,
                query
            )
            
            snippets = await conn.fetch(
                """
                SELECT id, citation, key_language, tags,
                       ts_rank(search_vector, plainto_tsquery('english', $1)) as rank
                FROM snippets
                WHERE search_vector @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT 10
                """,
                query
            )
            
            results["postgres"] = {
                "events": [dict(e) for e in events],
                "snippets": [dict(s) for s in snippets]
            }
    
    # Vector search in Qdrant
    if search_type in ["vector", "all"]:
        query_embedding = await get_embedding(query, openai_client)
        
        event_results = qdrant_client.search(
            collection_name="legal_events",
            query_vector=query_embedding,
            limit=10
        )
        
        snippet_results = qdrant_client.search(
            collection_name="legal_snippets",
            query_vector=query_embedding,
            limit=10
        )
        
        results["vector"] = {
            "events": [{"id": r.id, "score": r.score, **r.payload} for r in event_results],
            "snippets": [{"id": r.id, "score": r.score, **r.payload} for r in snippet_results]
        }
    
    # Knowledge graph search
    if search_type in ["knowledge_graph", "all"]:
        kg_results = await graphiti_client.search(query, num_results=20)
        results["knowledge_graph"] = [
            {
                "content": r.content,
                "source": r.source,
                "score": r.score,
                "id": r.id
            }
            for r in kg_results
        ]
    
    return results


async def postgres_full_text_search(
    postgres_pool: asyncpg.Pool,
    query: str,
    search_type: str = "all"
) -> Dict[str, Any]:
    """Advanced PostgreSQL full-text search with relevance ranking."""
    results = {}
    
    async with postgres_pool.acquire() as conn:
        if search_type in ["events", "all"]:
            events = await conn.fetch(
                """
                SELECT id, date, description, parties, tags, document_source,
                       ts_rank(search_vector, plainto_tsquery('english', $1)) as rank,
                       ts_headline('english', description, plainto_tsquery('english', $1),
                                 'StartSel=<mark>, StopSel=</mark>') as headline
                FROM events
                WHERE search_vector @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT 20
                """,
                query
            )
            results["events"] = [dict(e) for e in events]
        
        if search_type in ["snippets", "all"]:
            snippets = await conn.fetch(
                """
                SELECT id, citation, key_language, tags, case_type,
                       ts_rank(search_vector, plainto_tsquery('english', $1)) as rank,
                       ts_headline('english', key_language, plainto_tsquery('english', $1),
                                 'StartSel=<mark>, StopSel=</mark>') as headline
                FROM snippets
                WHERE search_vector @@ plainto_tsquery('english', $1)
                ORDER BY rank DESC
                LIMIT 20
                """,
                query
            )
            results["snippets"] = [dict(s) for s in snippets]
    
    return results


async def postgres_advanced_query(
    postgres_pool: asyncpg.Pool,
    sql_condition: str,
    target_table: str,
    parameters: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """Execute complex PostgreSQL queries with JSONB operations."""
    # Validate table name to prevent SQL injection
    if target_table not in ["events", "snippets"]:
        raise ValueError("Invalid target table")
    
    # Build safe query
    query = f"SELECT * FROM {target_table} WHERE {sql_condition}"
    
    async with postgres_pool.acquire() as conn:
        if parameters:
            results = await conn.fetch(query, *parameters.values())
        else:
            results = await conn.fetch(query)
    
    return [dict(r) for r in results]


async def ingest_legal_document(
    graphiti_client: Graphiti,
    document_text: str,
    title: str,
    date: str = None,
    document_type: str = None
) -> Dict[str, Any]:
    """Feed entire legal documents to Graphiti for automatic processing."""
    metadata = {
        "title": title,
        "document_type": document_type or "legal_document",
        "ingestion_date": datetime.now().isoformat()
    }
    
    if date:
        metadata["document_date"] = date
    
    # Process document through Graphiti
    result = await graphiti_client.add_episode(
        content=document_text,
        source=title,
        timestamp=datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    )
    
    return {
        "status": "success",
        "message": f"Document '{title}' ingested successfully",
        "entities_extracted": len(result.entity_edges) if hasattr(result, 'entity_edges') else 0,
        "relationships_created": len(result.episodic_edges) if hasattr(result, 'episodic_edges') else 0
    }


async def temporal_legal_query(
    graphiti_client: Graphiti,
    question: str,
    time_focus: str = None,
    entity_focus: str = None
) -> Dict[str, Any]:
    """Ask temporal questions about legal knowledge evolution."""
    # Build temporal query
    full_query = question
    if time_focus:
        full_query += f" Focus on the time period: {time_focus}"
    if entity_focus:
        full_query += f" Specifically regarding: {entity_focus}"
    
    # Search knowledge graph
    results = await graphiti_client.search(full_query, num_results=30)
    
    # Group results by time periods if available
    temporal_results = []
    for result in results:
        temporal_results.append({
            "content": result.content,
            "source": result.source,
            "timestamp": result.timestamp.isoformat() if hasattr(result, 'timestamp') else None,
            "relevance": result.score
        })
    
    # Sort by timestamp if available
    temporal_results.sort(
        key=lambda x: x["timestamp"] if x["timestamp"] else "9999",
        reverse=False
    )
    
    return {
        "question": question,
        "time_focus": time_focus,
        "entity_focus": entity_focus,
        "results": temporal_results,
        "total_results": len(temporal_results)
    }


async def create_manual_link(
    postgres_pool: asyncpg.Pool,
    event_id: str,
    snippet_id: str,
    relationship_type: str,
    confidence: float = 1.0,
    notes: str = None
) -> Dict[str, Any]:
    """Create explicit relationships between events and legal precedents."""
    async with postgres_pool.acquire() as conn:
        link_id = await conn.fetchval(
            """
            INSERT INTO manual_links (event_id, snippet_id, relationship_type, confidence, notes)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (event_id, snippet_id, relationship_type) 
            DO UPDATE SET confidence = $4, notes = $5
            RETURNING id
            """,
            uuid.UUID(event_id),
            uuid.UUID(snippet_id),
            relationship_type,
            confidence,
            notes
        )
    
    return {
        "link_id": str(link_id),
        "status": "success",
        "message": f"Manual link created: {relationship_type}"
    }


async def get_legal_analytics(postgres_pool: asyncpg.Pool) -> Dict[str, Any]:
    """Comprehensive legal research analytics using PostgreSQL power."""
    async with postgres_pool.acquire() as conn:
        # Party frequency analysis
        party_stats = await conn.fetch(
            """
            SELECT party, COUNT(*) as event_count
            FROM events, jsonb_array_elements_text(parties) as party
            GROUP BY party
            ORDER BY event_count DESC
            LIMIT 20
            """
        )
        
        # Tag trends
        tag_stats = await conn.fetch(
            """
            SELECT tag, COUNT(*) as usage_count
            FROM (
                SELECT jsonb_array_elements_text(tags) as tag FROM events
                UNION ALL
                SELECT jsonb_array_elements_text(tags) as tag FROM snippets
            ) t
            GROUP BY tag
            ORDER BY usage_count DESC
            LIMIT 20
            """
        )
        
        # Case type distribution
        case_types = await conn.fetch(
            """
            SELECT case_type, COUNT(*) as count
            FROM snippets
            WHERE case_type IS NOT NULL
            GROUP BY case_type
            ORDER BY count DESC
            """
        )
        
        # Events by year
        events_by_year = await conn.fetch(
            """
            SELECT EXTRACT(YEAR FROM date) as year, COUNT(*) as event_count
            FROM events
            GROUP BY year
            ORDER BY year
            """
        )
        
        # Relationship patterns
        link_stats = await conn.fetch(
            """
            SELECT relationship_type, COUNT(*) as count, AVG(confidence) as avg_confidence
            FROM manual_links
            GROUP BY relationship_type
            ORDER BY count DESC
            """
        )
    
    return {
        "party_frequency": [dict(p) for p in party_stats],
        "tag_trends": [dict(t) for t in tag_stats],
        "case_type_distribution": [dict(c) for c in case_types],
        "events_by_year": [dict(e) for e in events_by_year],
        "relationship_patterns": [dict(l) for l in link_stats],
        "generated_at": datetime.now().isoformat()
    }


async def get_system_status(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    neo4j_driver
) -> Dict[str, Any]:
    """Health check for all system components."""
    status = {}
    
    # Check PostgreSQL
    try:
        async with postgres_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            event_count = await conn.fetchval("SELECT COUNT(*) FROM events")
            snippet_count = await conn.fetchval("SELECT COUNT(*) FROM snippets")
        status["postgresql"] = {
            "status": "healthy",
            "event_count": event_count,
            "snippet_count": snippet_count
        }
    except Exception as e:
        status["postgresql"] = {"status": "error", "error": str(e)}
    
    # Check Qdrant
    try:
        collections = qdrant_client.get_collections()
        status["qdrant"] = {
            "status": "healthy",
            "collections": [c.name for c in collections.collections]
        }
    except Exception as e:
        status["qdrant"] = {"status": "error", "error": str(e)}
    
    # Check Neo4j
    try:
        with neo4j_driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
        status["neo4j"] = {
            "status": "healthy",
            "node_count": node_count
        }
    except Exception as e:
        status["neo4j"] = {"status": "error", "error": str(e)}
    
    status["capabilities"] = [
        "Timeline event management",
        "Legal snippet creation",
        "Hybrid search (PostgreSQL + Qdrant + Graphiti)",
        "Temporal legal queries",
        "Document ingestion with entity extraction",
        "Analytics and insights"
    ]
    
    return status