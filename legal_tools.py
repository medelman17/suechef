"""Implementation of legal research tools."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import asyncpg
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
import openai
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import (
    COMBINED_HYBRID_SEARCH_RRF,
    NODE_HYBRID_SEARCH_RRF,
    EDGE_HYBRID_SEARCH_RRF,
    COMMUNITY_HYBRID_SEARCH_RRF
)
import numpy as np

# Import custom legal entity types
from legal_entity_types import LEGAL_ENTITY_TYPES, LITIGATION_ENTITIES, RESEARCH_ENTITIES


async def get_embedding(text: str, openai_client) -> List[float]:
    """Get OpenAI embedding for text."""
    response = await openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding


def format_relationship_content(relationship_type: str, relationship_obj) -> str:
    """Convert raw relationship types into human-readable content."""
    
    # Try to get node names for context
    source_name = "Entity"
    target_name = "Entity"
    
    try:
        # Try multiple ways to get node names for context
        if hasattr(relationship_obj, 'source_node_name') and relationship_obj.source_node_name:
            source_name = relationship_obj.source_node_name
        elif hasattr(relationship_obj, 'source_node') and relationship_obj.source_node:
            source_name = str(relationship_obj.source_node)
        
        if hasattr(relationship_obj, 'target_node_name') and relationship_obj.target_node_name:
            target_name = relationship_obj.target_node_name
        elif hasattr(relationship_obj, 'target_node') and relationship_obj.target_node:
            target_name = str(relationship_obj.target_node)
            
        # Truncate very long names
        if len(source_name) > 50:
            source_name = source_name[:47] + "..."
        if len(target_name) > 50:
            target_name = target_name[:47] + "..."
            
    except Exception:
        pass
    
    # Map common relationship types to readable descriptions
    relationship_map = {
        "RESPONDS_UNDER_LEGAL_FRAMEWORK": f"Legal response framework connects {source_name} and {target_name}",
        "RESOLVED_WITH": f"Resolution mechanism: {source_name} resolved with {target_name}",
        "SMELLED_IN": f"Detection context: {source_name} detected in {target_name}",
        "LOCATED_IN": f"Location relationship: {source_name} located in {target_name}",
        "CAUSED_BY": f"Causal relationship: {source_name} caused by {target_name}",
        "INVOLVES": f"Involvement: {source_name} involves {target_name}",
        "APPLIES_TO": f"Application: {source_name} applies to {target_name}",
        "CITES": f"Citation: {source_name} cites {target_name}",
        "PRECEDENT_FOR": f"Precedent relationship: {source_name} is precedent for {target_name}",
        "PARTY_TO": f"Party relationship: {source_name} is party to {target_name}",
        "GOVERNS": f"Governance: {source_name} governs {target_name}",
        "OCCURRED_ON": f"Temporal relationship: {source_name} occurred on {target_name}",
        "VIOLATED": f"Violation: {source_name} violated {target_name}",
        "RESULTED_IN": f"Result: {source_name} resulted in {target_name}",
        "SUBJECT_TO": f"Subject relationship: {source_name} subject to {target_name}"
    }
    
    # Return mapped description or fallback to formatted type
    if relationship_type in relationship_map:
        return relationship_map[relationship_type]
    else:
        # Convert camelCase/snake_case to readable format
        readable_type = relationship_type.replace("_", " ").replace("-", " ").lower()
        return f"{readable_type.title()} relationship between {source_name} and {target_name}"


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
    significance: str = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Add a chronology event with automatic vector and knowledge graph storage."""
    
    # Insert into PostgreSQL
    async with postgres_pool.acquire() as conn:
        event_id = await conn.fetchval(
            """
            INSERT INTO events (date, description, parties, document_source, excerpts, tags, significance, group_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            datetime.strptime(date, "%Y-%m-%d").date(),
            description,
            json.dumps(parties or []),
            document_source,
            excerpts,
            json.dumps(tags or []),
            significance,
            group_id
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
                    "type": "event",
                    "group_id": group_id
                }
            )
        ]
    )
    
    # Add to Graphiti knowledge graph
    episode_content = f"On {date}: {description}"
    if excerpts:
        episode_content += f"\\nExcerpts: {excerpts}"
    
    await graphiti_client.add_episode(
        name=f"Legal Event - {date}",
        episode_body=episode_content,
        source=EpisodeType.text,
        source_description=document_source or "Legal Timeline",
        reference_time=datetime.strptime(date, "%Y-%m-%d"),
        group_id=group_id
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
    case_type: str = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Create a legal research snippet with automatic entity extraction."""
    
    # Insert into PostgreSQL
    async with postgres_pool.acquire() as conn:
        snippet_id = await conn.fetchval(
            """
            INSERT INTO snippets (citation, key_language, tags, context, case_type, group_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            citation,
            key_language,
            json.dumps(tags or []),
            context,
            case_type,
            group_id
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
                    "type": "snippet",
                    "group_id": group_id
                }
            )
        ]
    )
    
    # Add to Graphiti
    content = f"Legal Precedent: {citation}\\n{key_language}"
    if context:
        content += f"\\nContext: {context}"
    
    await graphiti_client.add_episode(
        name=f"Legal Snippet - {citation}",
        episode_body=content,
        source=EpisodeType.text,
        source_description=citation,
        reference_time=datetime.now(),
        group_id=group_id
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
    search_type: str = "all",
    group_id: str = "default"
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
        try:
            kg_results = await graphiti_client.search(
                query, 
                num_results=20,
                group_ids=[group_id] if group_id else None
            )
            
            # Handle Graphiti EntityEdge results
            graph_results = []
            for i, r in enumerate(kg_results):
                result_item = {
                    "id": str(r.uuid) if hasattr(r, 'uuid') else '',
                    "score": 1.0 / (i + 1),  # Simple relevance: order-based scoring
                    "type": "relationship"
                }
                
                # Extract relationship information with meaningful content
                if hasattr(r, 'fact') and r.fact:
                    # Prefer fact content as it's more descriptive
                    result_item["content"] = r.fact
                    result_item["relationship_type"] = getattr(r, 'name', "fact")
                elif hasattr(r, 'name') and r.name:
                    # Convert relationship type to readable content
                    result_item["relationship_type"] = r.name
                    result_item["content"] = format_relationship_content(r.name, r)
                else:
                    result_item["content"] = f"Knowledge graph relationship {str(r.uuid)[:8]}"
                    result_item["relationship_type"] = "unknown"
                
                # Add additional relationship context and metadata
                if hasattr(r, 'source_node_uuid') and hasattr(r, 'target_node_uuid'):
                    result_item["source_node"] = str(r.source_node_uuid)
                    result_item["target_node"] = str(r.target_node_uuid)
                
                if hasattr(r, 'group_id'):
                    result_item["group_id"] = r.group_id
                
                if hasattr(r, 'created_at'):
                    result_item["created_at"] = str(r.created_at)
                
                # Add any additional attributes for debugging
                if hasattr(r, 'attributes') and r.attributes:
                    result_item["attributes"] = r.attributes
                
                # Include episode context if available
                if hasattr(r, 'episode_uuid'):
                    result_item["episode_context"] = str(r.episode_uuid)
                
                graph_results.append(result_item)
            
            results["knowledge_graph"] = graph_results
            
        except Exception as e:
            # Graceful fallback if knowledge graph search fails
            results["knowledge_graph"] = []
            results["knowledge_graph_error"] = f"Search failed: {str(e)}"
    
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
        name=title,
        episode_body=document_text,
        source=EpisodeType.text,
        source_description=document_type or "Legal Document",
        reference_time=datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
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


# READ OPERATIONS

async def get_event(
    postgres_pool: asyncpg.Pool,
    event_id: str
) -> Dict[str, Any]:
    """Get a single event by ID."""
    async with postgres_pool.acquire() as conn:
        event = await conn.fetchrow(
            """
            SELECT id, date, description, parties, document_source, 
                   excerpts, tags, significance, created_at, updated_at
            FROM events
            WHERE id = $1
            """,
            uuid.UUID(event_id)
        )
        
        if not event:
            return {"error": f"Event {event_id} not found"}
        
        return dict(event)


async def get_snippet(
    postgres_pool: asyncpg.Pool,
    snippet_id: str
) -> Dict[str, Any]:
    """Get a single snippet by ID."""
    async with postgres_pool.acquire() as conn:
        snippet = await conn.fetchrow(
            """
            SELECT id, citation, key_language, tags, context, 
                   case_type, created_at, updated_at
            FROM snippets
            WHERE id = $1
            """,
            uuid.UUID(snippet_id)
        )
        
        if not snippet:
            return {"error": f"Snippet {snippet_id} not found"}
        
        return dict(snippet)


async def list_events(
    postgres_pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
    date_from: str = None,
    date_to: str = None,
    parties_filter: List[str] = None,
    tags_filter: List[str] = None
) -> Dict[str, Any]:
    """List events with optional filtering."""
    conditions = []
    params = []
    param_count = 0
    
    if date_from:
        param_count += 1
        conditions.append(f"date >= ${param_count}")
        params.append(datetime.strptime(date_from, "%Y-%m-%d").date())
    
    if date_to:
        param_count += 1
        conditions.append(f"date <= ${param_count}")
        params.append(datetime.strptime(date_to, "%Y-%m-%d").date())
    
    if parties_filter:
        param_count += 1
        conditions.append(f"parties ?| ${param_count}")
        params.append(parties_filter)
    
    if tags_filter:
        param_count += 1
        conditions.append(f"tags ?| ${param_count}")
        params.append(tags_filter)
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    async with postgres_pool.acquire() as conn:
        # Get total count
        count_query = f"SELECT COUNT(*) FROM events {where_clause}"
        total_count = await conn.fetchval(count_query, *params)
        
        # Get events
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        events_query = f"""
            SELECT id, date, description, parties, tags, 
                   document_source, significance
            FROM events
            {where_clause}
            ORDER BY date DESC, created_at DESC
            LIMIT ${param_count-1} OFFSET ${param_count}
        """
        
        events = await conn.fetch(events_query, *params)
        
        return {
            "events": [dict(e) for e in events],
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }


async def list_snippets(
    postgres_pool: asyncpg.Pool,
    limit: int = 50,
    offset: int = 0,
    case_type: str = None,
    tags_filter: List[str] = None
) -> Dict[str, Any]:
    """List snippets with optional filtering."""
    conditions = []
    params = []
    param_count = 0
    
    if case_type:
        param_count += 1
        conditions.append(f"case_type = ${param_count}")
        params.append(case_type)
    
    if tags_filter:
        param_count += 1
        conditions.append(f"tags ?| ${param_count}")
        params.append(tags_filter)
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    async with postgres_pool.acquire() as conn:
        # Get total count
        count_query = f"SELECT COUNT(*) FROM snippets {where_clause}"
        total_count = await conn.fetchval(count_query, *params)
        
        # Get snippets
        param_count += 1
        params.append(limit)
        param_count += 1
        params.append(offset)
        
        snippets_query = f"""
            SELECT id, citation, key_language, tags, case_type
            FROM snippets
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_count-1} OFFSET ${param_count}
        """
        
        snippets = await conn.fetch(snippets_query, *params)
        
        return {
            "snippets": [dict(s) for s in snippets],
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }


# UPDATE OPERATIONS

async def update_event(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    graphiti_client: Graphiti,
    openai_client,
    event_id: str,
    date: str = None,
    description: str = None,
    parties: List[str] = None,
    document_source: str = None,
    excerpts: str = None,
    tags: List[str] = None,
    significance: str = None
) -> Dict[str, Any]:
    """Update an existing event."""
    # Build update query dynamically
    updates = []
    params = []
    param_count = 0
    
    if date is not None:
        param_count += 1
        updates.append(f"date = ${param_count}")
        params.append(datetime.strptime(date, "%Y-%m-%d").date())
    
    if description is not None:
        param_count += 1
        updates.append(f"description = ${param_count}")
        params.append(description)
    
    if parties is not None:
        param_count += 1
        updates.append(f"parties = ${param_count}")
        params.append(json.dumps(parties))
    
    if document_source is not None:
        param_count += 1
        updates.append(f"document_source = ${param_count}")
        params.append(document_source)
    
    if excerpts is not None:
        param_count += 1
        updates.append(f"excerpts = ${param_count}")
        params.append(excerpts)
    
    if tags is not None:
        param_count += 1
        updates.append(f"tags = ${param_count}")
        params.append(json.dumps(tags))
    
    if significance is not None:
        param_count += 1
        updates.append(f"significance = ${param_count}")
        params.append(significance)
    
    if not updates:
        return {"error": "No fields to update"}
    
    param_count += 1
    params.append(uuid.UUID(event_id))
    
    async with postgres_pool.acquire() as conn:
        # Update PostgreSQL
        update_query = f"""
            UPDATE events
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, date, description, parties, document_source, excerpts, tags, significance
        """
        
        updated_event = await conn.fetchrow(update_query, *params)
        
        if not updated_event:
            return {"error": f"Event {event_id} not found"}
    
    # Update Qdrant if description, excerpts, or significance changed
    if description is not None or excerpts is not None or significance is not None:
        # Get full event data for embedding
        event_data = dict(updated_event)
        full_text = f"{event_data['description']} {event_data.get('excerpts', '')} {event_data.get('significance', '')}"
        embedding = await get_embedding(full_text, openai_client)
        
        qdrant_client.upsert(
            collection_name="legal_events",
            points=[
                PointStruct(
                    id=str(event_id),
                    vector=embedding,
                    payload={
                        "date": str(event_data['date']),
                        "description": event_data['description'],
                        "parties": json.loads(event_data['parties']),
                        "tags": json.loads(event_data['tags']),
                        "type": "event"
                    }
                )
            ]
        )
    
    return {
        "event_id": str(event_id),
        "status": "success",
        "message": "Event updated successfully",
        "updated_fields": list(updates)
    }


async def update_snippet(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    graphiti_client: Graphiti,
    openai_client,
    snippet_id: str,
    citation: str = None,
    key_language: str = None,
    tags: List[str] = None,
    context: str = None,
    case_type: str = None
) -> Dict[str, Any]:
    """Update an existing snippet."""
    # Build update query dynamically
    updates = []
    params = []
    param_count = 0
    
    if citation is not None:
        param_count += 1
        updates.append(f"citation = ${param_count}")
        params.append(citation)
    
    if key_language is not None:
        param_count += 1
        updates.append(f"key_language = ${param_count}")
        params.append(key_language)
    
    if tags is not None:
        param_count += 1
        updates.append(f"tags = ${param_count}")
        params.append(json.dumps(tags))
    
    if context is not None:
        param_count += 1
        updates.append(f"context = ${param_count}")
        params.append(context)
    
    if case_type is not None:
        param_count += 1
        updates.append(f"case_type = ${param_count}")
        params.append(case_type)
    
    if not updates:
        return {"error": "No fields to update"}
    
    param_count += 1
    params.append(uuid.UUID(snippet_id))
    
    async with postgres_pool.acquire() as conn:
        # Update PostgreSQL
        update_query = f"""
            UPDATE snippets
            SET {', '.join(updates)}
            WHERE id = ${param_count}
            RETURNING id, citation, key_language, tags, context, case_type
        """
        
        updated_snippet = await conn.fetchrow(update_query, *params)
        
        if not updated_snippet:
            return {"error": f"Snippet {snippet_id} not found"}
    
    # Update Qdrant if citation, key_language, or context changed
    if citation is not None or key_language is not None or context is not None:
        # Get full snippet data for embedding
        snippet_data = dict(updated_snippet)
        full_text = f"{snippet_data['citation']} {snippet_data['key_language']} {snippet_data.get('context', '')}"
        embedding = await get_embedding(full_text, openai_client)
        
        qdrant_client.upsert(
            collection_name="legal_snippets",
            points=[
                PointStruct(
                    id=str(snippet_id),
                    vector=embedding,
                    payload={
                        "citation": snippet_data['citation'],
                        "key_language": snippet_data['key_language'][:200],
                        "tags": json.loads(snippet_data['tags']),
                        "case_type": snippet_data.get('case_type'),
                        "type": "snippet"
                    }
                )
            ]
        )
    
    return {
        "snippet_id": str(snippet_id),
        "status": "success",
        "message": "Snippet updated successfully",
        "updated_fields": list(updates)
    }


# DELETE OPERATIONS

async def delete_event(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    event_id: str
) -> Dict[str, Any]:
    """Delete an event from all systems."""
    async with postgres_pool.acquire() as conn:
        # Delete from PostgreSQL (cascade will handle manual_links)
        deleted = await conn.fetchval(
            "DELETE FROM events WHERE id = $1 RETURNING id",
            uuid.UUID(event_id)
        )
        
        if not deleted:
            return {"error": f"Event {event_id} not found"}
    
    # Delete from Qdrant
    try:
        qdrant_client.delete(
            collection_name="legal_events",
            points_selector=[str(event_id)]
        )
    except Exception as e:
        # Log but don't fail if Qdrant delete fails
        pass
    
    # Note: Graphiti deletion would require additional implementation
    # as it doesn't have a direct delete by external ID method
    
    return {
        "event_id": str(event_id),
        "status": "success",
        "message": "Event deleted successfully"
    }


async def delete_snippet(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    snippet_id: str
) -> Dict[str, Any]:
    """Delete a snippet from all systems."""
    async with postgres_pool.acquire() as conn:
        # Delete from PostgreSQL (cascade will handle manual_links)
        deleted = await conn.fetchval(
            "DELETE FROM snippets WHERE id = $1 RETURNING id",
            uuid.UUID(snippet_id)
        )
        
        if not deleted:
            return {"error": f"Snippet {snippet_id} not found"}
    
    # Delete from Qdrant
    try:
        qdrant_client.delete(
            collection_name="legal_snippets",
            points_selector=[str(snippet_id)]
        )
    except Exception as e:
        # Log but don't fail if Qdrant delete fails
        pass
    
    return {
        "snippet_id": str(snippet_id),
        "status": "success",
        "message": "Snippet deleted successfully"
    }


async def build_legal_communities(
    graphiti_client: Graphiti,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Build communities in the knowledge graph to identify related legal concepts."""
    try:
        # Build communities with optional group filtering
        community_results = await graphiti_client.build_communities(
            group_ids=[group_id] if group_id else None
        )
        
        return {
            "status": "success",
            "message": "Legal communities built successfully",
            "communities_created": len(community_results) if community_results else 0,
            "group_id": group_id
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to build communities: {str(e)}"
        }


async def search_legal_communities(
    graphiti_client: Graphiti,
    query: str,
    group_id: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """Search for communities related to a legal query."""
    try:
        # Use predefined community search recipe
        results = await graphiti_client._search(
            query=query,
            config=COMMUNITY_HYBRID_SEARCH_RRF
        )
        
        communities = []
        if results.communities:
            for community in results.communities:
                communities.append({
                    "id": community.id,
                    "summary": getattr(community, 'summary', ''),
                    "size": getattr(community, 'size', 0),
                    "relevance_score": getattr(community, 'score', 0.0)
                })
        
        return {
            "status": "success",
            "query": query,
            "group_id": group_id,
            "communities": communities,
            "total_found": len(communities)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Community search failed: {str(e)}"
        }


async def enhanced_legal_search(
    postgres_pool: asyncpg.Pool,
    qdrant_client,
    graphiti_client: Graphiti,
    openai_client,
    query: str,
    search_focus: str = "hybrid",  # hybrid, nodes, edges, communities
    group_id: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Enhanced search using SearchConfig for configurable retrieval."""
    try:
        results = {"query": query, "group_id": group_id, "search_focus": search_focus}
        
        # Graphiti enhanced search with predefined recipes
        if search_focus in ["hybrid", "nodes", "edges", "communities"]:
            # Select appropriate search recipe based on focus
            config_map = {
                "nodes": NODE_HYBRID_SEARCH_RRF,
                "edges": EDGE_HYBRID_SEARCH_RRF,
                "communities": COMMUNITY_HYBRID_SEARCH_RRF,
                "hybrid": COMBINED_HYBRID_SEARCH_RRF
            }
            
            selected_config = config_map.get(search_focus, COMBINED_HYBRID_SEARCH_RRF)
            
            kg_results = await graphiti_client._search(
                query=query,
                config=selected_config
            )
            
            # Process nodes
            if kg_results.nodes:
                results["nodes"] = [
                    {
                        "id": node.id,
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "attributes": getattr(node, 'attributes', {}),
                        "score": getattr(node, 'score', 0.0)
                    }
                    for node in kg_results.nodes
                ]
            
            # Process edges (relationships)
            if kg_results.edges:
                results["edges"] = [
                    {
                        "id": edge.id,
                        "source": getattr(edge, 'source_node_id', ''),
                        "target": getattr(edge, 'target_node_id', ''),
                        "relation_type": getattr(edge, 'relation_type', ''),
                        "score": getattr(edge, 'score', 0.0)
                    }
                    for edge in kg_results.edges
                ]
            
            # Process communities
            if kg_results.communities:
                results["communities"] = [
                    {
                        "id": community.id,
                        "summary": getattr(community, 'summary', ''),
                        "size": getattr(community, 'size', 0),
                        "score": getattr(community, 'score', 0.0)
                    }
                    for community in kg_results.communities
                ]
        
        # Add traditional hybrid search for comparison
        if search_focus == "hybrid":
            traditional_results = await unified_legal_search(
                postgres_pool, qdrant_client, graphiti_client, openai_client,
                query, "all", group_id
            )
            results["traditional_search"] = traditional_results
        
        return {
            "status": "success",
            "results": results
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Enhanced search failed: {str(e)}"
        }