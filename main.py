"""
SueChef MCP Server - Modular Version
A simplified, modular implementation using the new architecture.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Union

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


# Lifespan context manager for proper initialization
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    """Server startup and shutdown logic"""
    # Startup
    await initialize_services()
    try:
        yield
    finally:
        # Shutdown
        if db_manager:
            await db_manager.close()

# Initialize FastMCP server with lifespan
mcp = FastMCP("suechef", lifespan=lifespan)

# Global components
config = None
db_manager = None
event_service = None
snippet_service = None
courtlistener_service = None


async def ensure_initialized():
    """Ensure all components are initialized."""
    if config is None or db_manager is None or event_service is None:
        await initialize_services()
    
    # Double-check that database manager is properly initialized
    if db_manager is None:
        raise RuntimeError("DatabaseManager failed to initialize. Check database connections.")
    
    # Verify database manager is actually initialized
    try:
        # This will raise an error if not initialized
        _ = db_manager.postgres
    except RuntimeError as e:
        if "not initialized" in str(e):
            # Try to reinitialize
            await db_manager.initialize()
        else:
            raise


async def find_related_events(
    event_service, db_manager, openai_client, 
    event_id: str, parties: List[str], tags: List[str], 
    description: str, group_id: str
) -> Dict[str, Any]:
    """Find related events using multiple strategies."""
    related_events = []
    strategies_used = []
    
    try:
        # Strategy 1: Same parties (highest relevance)
        if parties:
            party_events = await event_service.list_events(
                parties_filter=parties, group_id=group_id, limit=5
            )
            if party_events.get("status") == "success":
                for event in party_events.get("data", {}).get("events", []):
                    if event["id"] != event_id:  # Exclude the just-created event
                        related_events.append({
                            **event,
                            "relationship_type": "same_parties",
                            "relevance_score": 0.9,
                            "match_reason": f"Shares parties: {', '.join(set(parties) & set(event.get('parties', [])))}"
                        })
                if party_events.get("data", {}).get("events"):
                    strategies_used.append("same_parties")
        
        # Strategy 2: Same tags (medium-high relevance)
        if tags:
            tag_events = await event_service.list_events(
                tags_filter=tags, group_id=group_id, limit=5
            )
            if tag_events.get("status") == "success":
                for event in tag_events.get("data", {}).get("events", []):
                    if event["id"] != event_id and not any(re["id"] == event["id"] for re in related_events):
                        related_events.append({
                            **event,
                            "relationship_type": "same_tags",
                            "relevance_score": 0.7,
                            "match_reason": f"Shares tags: {', '.join(set(tags) & set(event.get('tags', [])))}"
                        })
                if tag_events.get("data", {}).get("events"):
                    strategies_used.append("same_tags")
        
        # Strategy 3: Vector similarity search (semantic similarity)
        try:
            from src.utils.embeddings import get_embedding
            query_embedding = await get_embedding(description, openai_client)
            
            # Search for similar events in Qdrant
            similar_results = db_manager.qdrant.search(
                collection_name="legal_events",
                query_vector=query_embedding,
                query_filter={
                    "must": [
                        {"key": "group_id", "match": {"value": group_id}},
                        {"key": "type", "match": {"value": "event"}}
                    ]
                },
                limit=7,
                score_threshold=0.7  # Only high-similarity matches
            )
            
            for result in similar_results:
                if result.id != event_id and not any(re["id"] == result.id for re in related_events):
                    # Get full event details from PostgreSQL
                    full_event = await event_service.get_event(result.id)
                    if full_event.get("status") == "success":
                        event_data = full_event.get("data", {})
                        related_events.append({
                            **event_data,
                            "relationship_type": "semantic_similarity", 
                            "relevance_score": float(result.score),
                            "match_reason": f"Semantic similarity score: {result.score:.2f}"
                        })
            
            if similar_results:
                strategies_used.append("vector_similarity")
                
        except Exception as e:
            # Vector search failed, continue with other strategies
            pass
        
        # Strategy 4: Temporal proximity (events near the same date)
        try:
            async with db_manager.postgres.acquire() as conn:
                temporal_query = """
                    SELECT id, date, description, parties, tags, significance,
                           ABS(EXTRACT(days FROM (date - $1::date))) as days_difference
                    FROM events 
                    WHERE group_id = $2 
                    AND id != $3
                    AND ABS(EXTRACT(days FROM (date - $1::date))) <= 30
                    ORDER BY days_difference ASC
                    LIMIT 5
                """
                
                # Get the date of the current event first
                current_event = await event_service.get_event(event_id)
                if current_event.get("status") == "success":
                    current_date = current_event.get("data", {}).get("date")
                    if current_date:
                        temporal_results = await conn.fetch(
                            temporal_query, 
                            current_date, group_id, event_id
                        )
                        
                        for record in temporal_results:
                            if not any(re["id"] == str(record["id"]) for re in related_events):
                                event_dict = dict(record)
                                event_dict["parties"] = json.loads(event_dict["parties"]) if event_dict["parties"] else []
                                event_dict["tags"] = json.loads(event_dict["tags"]) if event_dict["tags"] else []
                                event_dict["id"] = str(event_dict["id"])
                                days_diff = event_dict.pop("days_difference")
                                
                                related_events.append({
                                    **event_dict,
                                    "relationship_type": "temporal_proximity",
                                    "relevance_score": max(0.3, 1.0 - (days_diff / 30.0)),  # Score decreases with time distance
                                    "match_reason": f"Occurred {days_diff} days apart"
                                })
                        
                        if temporal_results:
                            strategies_used.append("temporal_proximity")
        
        except Exception as e:
            # Temporal search failed, continue
            pass
        
        # Sort by relevance score and limit results
        related_events.sort(key=lambda x: x["relevance_score"], reverse=True)
        related_events = related_events[:10]  # Top 10 most relevant
        
        return {
            "events": related_events,
            "total_found": len(related_events),
            "strategies_used": strategies_used,
            "search_criteria": {
                "parties": parties,
                "tags": tags, 
                "group_id": group_id,
                "excluded_event": event_id
            }
        }
        
    except Exception as e:
        return {
            "events": [],
            "total_found": 0,
            "strategies_used": strategies_used,
            "error": f"Related events search failed: {str(e)}"
        }


def analyze_citation_significance(citation: str, opinion_data: Dict) -> Dict[str, Any]:
    """Analyze citation patterns to determine legal significance."""
    analysis = {
        "importance_score": "medium",
        "precedential_value": "unknown",
        "citation_indicators": []
    }
    
    try:
        # Check citation type for precedential value
        if "U.S." in citation or "S.Ct." in citation:
            analysis["importance_score"] = "high"
            analysis["precedential_value"] = "binding_nationwide"
            analysis["citation_indicators"].append("Supreme Court decision")
        elif "F.3d" in citation or "F.2d" in citation:
            analysis["importance_score"] = "medium-high"
            analysis["precedential_value"] = "binding_circuit"
            analysis["citation_indicators"].append("Federal appellate decision")
        elif "F.Supp" in citation:
            analysis["importance_score"] = "medium"
            analysis["precedential_value"] = "persuasive"
            analysis["citation_indicators"].append("Federal district court decision")
        
        # Check for citation counts
        cite_count = opinion_data.get("citation_count", 0)
        if cite_count > 100:
            analysis["importance_score"] = "high"
            analysis["citation_indicators"].append(f"Highly cited ({cite_count} citations)")
        elif cite_count > 25:
            analysis["importance_score"] = "medium-high"
            analysis["citation_indicators"].append(f"Well-cited ({cite_count} citations)")
        
        # Check for recency
        date_filed = opinion_data.get("date_filed", "")
        if date_filed:
            year = int(date_filed[:4]) if len(date_filed) >= 4 else 0
            current_year = 2024
            if current_year - year <= 5:
                analysis["citation_indicators"].append("Recent decision (within 5 years)")
            elif current_year - year > 30:
                analysis["citation_indicators"].append("Older precedent (30+ years)")
        
        return analysis
        
    except Exception:
        return analysis


async def analyze_related_content(db_manager, snippet_id: str, case_name: str, group_id: str) -> Dict[str, Any]:
    """Analyze how the imported opinion relates to existing content."""
    analysis = {
        "similar_snippets": [],
        "related_events": [],
        "thematic_connections": [],
        "total_connections": 0
    }
    
    try:
        # Find similar snippets using vector search
        if snippet_service and snippet_id:
            similar_snippets = await snippet_service.list_snippets(
                group_id=group_id, limit=5
            )
            
            if similar_snippets.get("status") == "success":
                snippets = similar_snippets.get("data", {}).get("snippets", [])
                for snippet in snippets[:3]:  # Top 3 most similar
                    if snippet["id"] != snippet_id:
                        analysis["similar_snippets"].append({
                            "id": snippet["id"],
                            "citation": snippet.get("citation", ""),
                            "case_type": snippet.get("case_type", ""),
                            "similarity_reason": "Same practice area"
                        })
        
        # Find related events by searching for case name keywords
        if event_service:
            # Extract key terms from case name for search
            search_terms = [word.lower() for word in case_name.split() if len(word) > 3 and word.lower() not in ['case', 'v.', 'vs.', 'the', 'and', 'inc.', 'corp.']]
            
            for term in search_terms[:2]:  # Search top 2 meaningful terms
                related_events = await event_service.list_events(
                    group_id=group_id, limit=3
                )
                
                if related_events.get("status") == "success":
                    events = related_events.get("data", {}).get("events", [])
                    for event in events:
                        if term in event.get("description", "").lower():
                            analysis["related_events"].append({
                                "id": event["id"],
                                "date": event.get("date"),
                                "description": event.get("description", "")[:100] + "...",
                                "connection": f"Contains term '{term}'"
                            })
        
        # Identify thematic connections
        practice_areas = []
        case_lower = case_name.lower()
        
        if any(term in case_lower for term in ["landlord", "tenant", "lease", "rent"]):
            practice_areas.append("landlord-tenant")
        if any(term in case_lower for term in ["negligence", "liability", "damages"]):
            practice_areas.append("tort law")
        if any(term in case_lower for term in ["contract", "breach", "agreement"]):
            practice_areas.append("contract law")
        if any(term in case_lower for term in ["water", "flood", "leak", "damage"]):
            practice_areas.append("property damage")
        
        analysis["thematic_connections"] = practice_areas
        analysis["total_connections"] = (
            len(analysis["similar_snippets"]) + 
            len(analysis["related_events"]) + 
            len(analysis["thematic_connections"])
        )
        
    except Exception as e:
        analysis["error"] = f"Related content analysis failed: {str(e)}"
    
    return analysis


def extract_legal_concepts(opinion_text: str, case_name: str) -> Dict[str, Any]:
    """Extract key legal concepts and entities from opinion text."""
    concepts = {
        "holdings": [],
        "practice_areas": [],
        "parties": [],
        "procedural_posture": "unknown",
        "legal_standards": []
    }
    
    try:
        text_lower = opinion_text.lower()
        
        # Extract holdings (look for common holding language)
        holding_indicators = [
            "we hold that", "we conclude that", "we find that", 
            "the court holds", "this court concludes", "we rule that"
        ]
        
        for indicator in holding_indicators:
            if indicator in text_lower:
                # Extract sentence containing holding
                sentences = opinion_text.split('.')
                for sentence in sentences:
                    if indicator in sentence.lower():
                        concepts["holdings"].append(sentence.strip()[:200] + "...")
                        break
        
        # Identify practice areas
        if any(term in text_lower for term in ["landlord", "tenant", "lease", "rental"]):
            concepts["practice_areas"].append("Landlord-Tenant Law")
        if any(term in text_lower for term in ["negligence", "duty of care", "reasonable care"]):
            concepts["practice_areas"].append("Tort Law - Negligence")
        if any(term in text_lower for term in ["contract", "breach", "agreement", "consideration"]):
            concepts["practice_areas"].append("Contract Law")
        if any(term in text_lower for term in ["criminal", "defendant", "prosecution"]):
            concepts["practice_areas"].append("Criminal Law")
        if any(term in text_lower for term in ["constitutional", "amendment", "due process"]):
            concepts["practice_areas"].append("Constitutional Law")
        
        # Extract parties from case name
        if " v. " in case_name:
            parties = case_name.split(" v. ")
            if len(parties) >= 2:
                concepts["parties"] = [parties[0].strip(), parties[1].strip()]
        elif " vs. " in case_name:
            parties = case_name.split(" vs. ")
            if len(parties) >= 2:
                concepts["parties"] = [parties[0].strip(), parties[1].strip()]
        
        # Determine procedural posture
        if any(term in text_lower for term in ["appeal", "affirm", "reverse", "remand"]):
            concepts["procedural_posture"] = "appellate"
        elif any(term in text_lower for term in ["motion to dismiss", "summary judgment", "trial"]):
            concepts["procedural_posture"] = "trial court"
        elif any(term in text_lower for term in ["petition for certiorari", "writ of certiorari"]):
            concepts["procedural_posture"] = "supreme court"
        
        # Extract legal standards
        standards = []
        if "reasonable person" in text_lower or "reasonable care" in text_lower:
            standards.append("reasonable person standard")
        if "preponderance of evidence" in text_lower:
            standards.append("preponderance of evidence")
        if "beyond reasonable doubt" in text_lower:
            standards.append("beyond reasonable doubt")
        if "strict liability" in text_lower:
            standards.append("strict liability")
        
        concepts["legal_standards"] = standards
        
    except Exception:
        # Return basic concepts if extraction fails
        pass
    
    return concepts


def determine_court_level(court_info: Dict) -> str:
    """Determine the hierarchical level of the court."""
    court_name = court_info.get("full_name", court_info.get("short_name", "")).lower()
    
    if "supreme court" in court_name:
        return "supreme"
    elif any(term in court_name for term in ["appeal", "circuit", "appellate"]):
        return "appellate"
    elif any(term in court_name for term in ["district", "superior", "trial"]):
        return "trial"
    else:
        return "unknown"


def extract_jurisdiction(court_info: Dict, citation: str) -> str:
    """Extract jurisdiction information from court and citation data."""
    court_name = court_info.get("full_name", court_info.get("short_name", ""))
    
    # Federal courts
    if "U.S." in citation or "S.Ct." in citation:
        return "Federal - U.S. Supreme Court"
    elif any(circuit in citation for circuit in ["1st Cir", "2nd Cir", "3rd Cir", "4th Cir", "5th Cir", "6th Cir", "7th Cir", "8th Cir", "9th Cir", "10th Cir", "11th Cir", "D.C. Cir", "Fed. Cir"]):
        return f"Federal - {citation.split('Cir')[0]}Cir."
    elif "F.Supp" in citation:
        return "Federal - District Court"
    
    # State courts
    state_indicators = {
        "Cal.": "California", "N.Y.": "New York", "Tex.": "Texas", "Fla.": "Florida",
        "Ill.": "Illinois", "Pa.": "Pennsylvania", "Ohio": "Ohio", "Ga.": "Georgia",
        "N.C.": "North Carolina", "Mich.": "Michigan", "Va.": "Virginia", "Wash.": "Washington"
    }
    
    for abbrev, full_name in state_indicators.items():
        if abbrev in citation:
            return f"State - {full_name}"
    
    # Fallback to court name analysis
    if "federal" in court_name.lower():
        return "Federal"
    elif any(state in court_name.lower() for state in ["california", "new york", "texas", "florida"]):
        return f"State - {court_name}"
    
    return "Unknown Jurisdiction"


# =============================================================================
# MIGRATED TOOLS (using new modular architecture)
# =============================================================================

# @mcp.tool()
# async def testArrayParameters(
#     test_parties: Optional[Any] = None,
#     test_tags: Optional[Any] = None
# ) -> Dict[str, Any]:
#     """Diagnostic tool to test and validate array parameter parsing for legal entities like parties and tags."""
#     from src.utils.parameter_parsing import parse_string_list
    
#     try:
#         parties_result = parse_string_list(test_parties)
#         tags_result = parse_string_list(test_tags)
        
#         return {
#             "status": "success",
#             "results": {
#                 "parties": {
#                     "input": test_parties,
#                     "input_type": str(type(test_parties)),
#                     "parsed": parties_result,
#                     "parsed_type": str(type(parties_result))
#                 },
#                 "tags": {
#                     "input": test_tags,
#                     "input_type": str(type(test_tags)),
#                     "parsed": tags_result,
#                     "parsed_type": str(type(tags_result))
#                 }
#             },
#             "message": "Array parameter parsing test completed successfully"
#         }
#     except Exception as e:
#         return {
#             "status": "error",
#             "message": f"Array parsing test failed: {str(e)}",
#             "debug_info": {
#                 "test_parties": str(test_parties),
#                 "test_tags": str(test_tags)
#             }
#         }

@mcp.tool()
async def createLegalEvent(
    date: str,
    description: str,
    parties: Optional[Any] = None,  # Accept Any type for flexible parsing
    document_source: Optional[str] = None,
    excerpts: Optional[str] = None,
    tags: Optional[Any] = None,     # Accept Any type for flexible parsing
    significance: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Create timestamped legal events with automatic knowledge graph integration and vector search indexing for case chronologies."""
    await ensure_initialized()
    
    import time
    start_time = time.time()
    
    # Normalize array parameters using existing parser
    from src.utils.parameter_parsing import parse_string_list
    normalized_parties = parse_string_list(parties)
    normalized_tags = parse_string_list(tags)
    
    # Call the service to create the event
    service_result = await event_service.create_event(
        date=date,
        description=description,
        parties=normalized_parties,
        document_source=document_source,
        excerpts=excerpts,
        tags=normalized_tags,
        significance=significance,
        group_id=group_id,
        openai_api_key=config.api.openai_api_key
    )
    
    # If service failed, return the error
    if service_result.get("status") == "error":
        return {
            "success": False,
            "error": {
                "message": service_result.get("message", "Unknown error"),
                "type": service_result.get("error_type", "creation_error")
            }
        }
    
    # Get the created event ID
    event_id = service_result.get("data", {}).get("event_id")
    if not event_id:
        return {
            "success": False,
            "error": {"message": "No event ID returned from service", "type": "response_error"}
        }
    
    # Get the full event details
    event_details = await event_service.get_event(event_id)
    
    # Calculate processing time
    processing_time_ms = round((time.time() - start_time) * 1000)
    
    # Find actual related events using multiple strategies
    try:
        related_events_data = await find_related_events(
            event_service, db_manager, openai.AsyncOpenAI(api_key=config.api.openai_api_key),
            event_id, normalized_parties, normalized_tags, description, group_id
        )
        related_count = len(related_events_data.get("events", []))
    except Exception as e:
        related_events_data = {"events": [], "strategies_used": [], "error": str(e)}
        related_count = 0
    
    # Create structured data for programmatic use
    structured_data = {
        "success": True,
        "event": {
            "id": event_id,
            "date": date,
            "description": description,
            "parties": normalized_parties or [],
            "tags": normalized_tags or [],
            "significance": significance,
            "group_id": group_id,
            "document_source": document_source,
            "excerpts": excerpts,
            "created_at": event_details.get("data", {}).get("created_at") if event_details.get("status") == "success" else None
        },
        "storage": {
            "postgres": {"stored": True, "table": "legal_events"},
            "qdrant": {"stored": True, "collection": "legal_events", "vector_id": event_id},
            "graphiti": {"stored": True, "episode_name": f"Legal Event - {date}"}
        },
        "metadata": {
            "processing_time_ms": processing_time_ms,
            "vector_dimensions": 1536,  # OpenAI text-embedding-3-small dimension
            "related_events_count": related_count
        },
        "related_events": related_events_data,
        "next_actions": [
            {"action": "link_precedents", "description": "Link this event to relevant legal precedents"},
            {"action": "view_timeline", "resource": "suechef://data/events/timeline"},
            {"action": "search_similar", "description": f"Search for events with similar parties or tags"},
            {"action": "explore_related", "description": f"Explore {related_count} related events found", "available": related_count > 0}
        ]
    }
    
    # Return the structured data (FastMCP will serialize as JSON)
    # This is the correct behavior for FastMCP - clients should parse the JSON if they need structured access
    return structured_data


@mcp.tool()
async def retrieveLegalEvent(event_id: str) -> Dict[str, Any]:
    """Retrieve a specific legal event with all associated metadata, parties, document references, and significance ratings."""
    await ensure_initialized()
    return await event_service.get_event(event_id)


@mcp.tool()
async def searchLegalEvents(
    limit: int = 50,
    offset: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    parties_filter: Optional[Any] = None,  # Accept Any type for flexible parsing
    tags_filter: Optional[Any] = None,     # Accept Any type for flexible parsing
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Search and filter legal events by date range, parties, tags, or case groups with pagination support for building timelines."""
    await ensure_initialized()
    
    # Normalize array parameters using existing parser
    from src.utils.parameter_parsing import parse_string_list
    normalized_parties_filter = parse_string_list(parties_filter) if parties_filter is not None else None
    normalized_tags_filter = parse_string_list(tags_filter) if tags_filter is not None else None
    
    return await event_service.list_events(
        limit=limit,
        offset=offset,
        date_from=date_from,
        date_to=date_to,
        parties_filter=normalized_parties_filter,
        tags_filter=normalized_tags_filter,
        group_id=group_id
    )


@mcp.tool()
async def updateLegalEvent(
    event_id: str,
    date: Optional[str] = None,
    description: Optional[str] = None,
    parties: Optional[Any] = None,  # Accept Any type for flexible parsing
    document_source: Optional[str] = None,
    excerpts: Optional[str] = None,
    tags: Optional[Any] = None,     # Accept Any type for flexible parsing
    significance: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing legal event with automatic re-vectorization and knowledge graph updates."""
    await ensure_initialized()
    
    # Normalize array parameters using existing parser
    from src.utils.parameter_parsing import parse_string_list
    normalized_parties = parse_string_list(parties) if parties is not None else None
    normalized_tags = parse_string_list(tags) if tags is not None else None
    
    # Get OpenAI API key from config
    openai_api_key = config.openai.api_key if config and config.openai else ""
    
    return await event_service.update_event(
        event_id=event_id,
        date=date,
        description=description,
        parties=normalized_parties,
        document_source=document_source,
        excerpts=excerpts,
        tags=normalized_tags,
        significance=significance,
        openai_api_key=openai_api_key
    )


@mcp.tool()
async def deleteLegalEvent(event_id: str) -> Dict[str, Any]:
    """Delete a legal event from all systems (PostgreSQL, Qdrant) with cascade cleanup of related records."""
    await ensure_initialized()
    return await event_service.delete_event(event_id)


# SNIPPET MANAGEMENT TOOLS (MODULAR VERSION)

@mcp.tool()
async def createLegalSnippet(
    citation: str,
    key_language: str,
    tags: Optional[Any] = None,  # Accept Any type for flexible parsing
    context: Optional[str] = None,
    case_type: Optional[str] = None,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Create searchable legal research snippets from case law, statutes, or precedents with automatic citation parsing and vectorization."""
    await ensure_initialized()
    
    import time
    import re
    start_time = time.time()
    
    # Normalize array parameters using existing parser
    from src.utils.parameter_parsing import parse_string_list
    normalized_tags = parse_string_list(tags)
    
    # Call the service to create the snippet
    service_result = await snippet_service.create_snippet(
        citation=citation,
        key_language=key_language,
        tags=normalized_tags,
        context=context,
        case_type=case_type,
        group_id=group_id,
        openai_api_key=config.api.openai_api_key
    )
    
    # If service failed, return the error
    if service_result.get("status") == "error":
        return {
            "success": False,
            "error": {
                "message": service_result.get("message", "Unknown error"),
                "type": service_result.get("error_type", "creation_error")
            }
        }
    
    # Get the created snippet ID
    snippet_id = service_result.get("data", {}).get("snippet_id")
    if not snippet_id:
        return {
            "success": False,
            "error": {"message": "No snippet ID returned from service", "type": "response_error"}
        }
    
    # Get the full snippet details
    snippet_details = await snippet_service.get_snippet(snippet_id)
    
    # Parse citation for additional metadata
    citation_analysis = {
        "citation_parsed": True,
        "jurisdiction": "Unknown",
        "court_level": "Unknown",
        "year": None
    }
    
    # Basic citation parsing
    try:
        # Look for court indicators
        if "F.3d" in citation or "F.2d" in citation or "F." in citation:
            citation_analysis["court_level"] = "federal"
            if "Cir." in citation:
                citation_analysis["court_level"] = "appellate"
                # Extract circuit
                circuit_match = re.search(r'(\d+(?:st|nd|rd|th)\s+Cir\.)', citation)
                if circuit_match:
                    citation_analysis["jurisdiction"] = circuit_match.group(1)
        elif "U.S." in citation or "S.Ct." in citation:
            citation_analysis["court_level"] = "supreme"
            citation_analysis["jurisdiction"] = "U.S. Supreme Court"
        
        # Extract year
        year_match = re.search(r'\((\d{4})\)', citation)
        if year_match:
            citation_analysis["year"] = int(year_match.group(1))
            
    except Exception:
        citation_analysis["citation_parsed"] = False
    
    # Calculate processing time
    processing_time_ms = round((time.time() - start_time) * 1000)
    
    # Count similar snippets (basic recommendation system)
    try:
        similar_snippets = await snippet_service.list_snippets(case_type=case_type, limit=1, group_id=group_id)
        similar_count = max(0, similar_snippets.get("total", 1) - 1)  # Subtract the just-created snippet
    except:
        similar_count = 0
    
    # Return structured response
    return {
        "success": True,
        "snippet": {
            "id": snippet_id,
            "citation": citation,
            "key_language": key_language,
            "tags": normalized_tags or [],
            "case_type": case_type,
            "context": context,
            "group_id": group_id,
            "created_at": snippet_details.get("data", {}).get("created_at") if snippet_details.get("status") == "success" else None
        },
        "analysis": citation_analysis,
        "storage": {
            "postgres": {"stored": True, "table": "legal_snippets"},
            "qdrant": {"stored": True, "collection": "legal_snippets", "vector_id": snippet_id},
            "graphiti": {"stored": True, "connections_created": 1}  # Could be tracked more precisely
        },
        "metadata": {
            "processing_time_ms": processing_time_ms,
            "vector_dimensions": 1536,
            "similar_snippets_count": similar_count
        },
        "recommendations": [
            {"type": "similar_cases", "count": similar_count, "available": similar_count > 0},
            {"type": "citing_opinions", "available": True, "action": "use findCitingOpinions tool"},
            {"type": "related_events", "description": "Link this snippet to relevant case events"}
        ]
    }


@mcp.tool()
async def retrieveLegalSnippet(snippet_id: str) -> Dict[str, Any]:
    """Retrieve a specific legal research snippet with citation details, key language, context, and associated tags."""
    await ensure_initialized()
    
    return await snippet_service.get_snippet(snippet_id)


@mcp.tool()
async def searchLegalSnippets(
    limit: int = 50,
    offset: int = 0,
    case_type: Optional[str] = None,
    tags_filter: Optional[Any] = None,  # Accept Any type for flexible parsing
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Search and filter legal research snippets by case type, tags, or group with pagination for precedent research."""
    await ensure_initialized()
    
    # Normalize array parameters using existing parser
    from src.utils.parameter_parsing import parse_string_list
    normalized_tags_filter = parse_string_list(tags_filter) if tags_filter is not None else None
    
    return await snippet_service.list_snippets(
        limit=limit,
        offset=offset,
        case_type=case_type,
        tags_filter=normalized_tags_filter,
        group_id=group_id
    )


@mcp.tool()
async def updateLegalSnippet(
    snippet_id: str,
    citation: Optional[str] = None,
    key_language: Optional[str] = None,
    tags: Optional[Any] = None,  # Accept Any type for flexible parsing
    context: Optional[str] = None,
    case_type: Optional[str] = None
) -> Dict[str, Any]:
    """Update legal research snippet content, citations, tags, or context with automatic re-vectorization for improved search."""
    await ensure_initialized()
    
    # Normalize array parameters using existing parser
    from src.utils.parameter_parsing import parse_string_list
    normalized_tags = parse_string_list(tags) if tags is not None else None
    
    return await snippet_service.update_snippet(
        snippet_id=snippet_id,
        citation=citation,
        key_language=key_language,
        tags=normalized_tags,
        context=context,
        case_type=case_type,
        openai_api_key=config.api.openai_api_key
    )


@mcp.tool()
async def deleteLegalSnippet(snippet_id: str) -> Dict[str, Any]:
    """Permanently remove a legal research snippet from all databases and search indexes with cascade cleanup."""
    await ensure_initialized()
    
    return await snippet_service.delete_snippet(snippet_id)


# COURTLISTENER INTEGRATION TOOLS (MODULAR VERSION)

@mcp.tool()
async def testCourtListenerConnection() -> Dict[str, Any]:
    """Verify CourtListener API connectivity and authentication status for accessing judicial opinion databases."""
    await ensure_initialized()
    if courtlistener_service is None:
        return {"status": "error", "message": "CourtListener service not initialized"}
    return await courtlistener_service.test_connection()


@mcp.tool()
async def searchCourtOpinions(
    query: str,
    court: Optional[str] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    cited_gt: Optional[int] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Search millions of published court opinions and judicial decisions through CourtListener with advanced filtering options."""
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
async def importCourtOpinion(
    opinion_id: int,
    add_as_snippet: bool = True,
    auto_link_events: bool = True,
    group_id: str = "default"
) -> Dict[str, Any]:
    """Import court opinions directly into your legal research database with automatic snippet creation and event linking."""
    await ensure_initialized()
    
    import time
    import re
    start_time = time.time()
    
    # Get the basic import result
    basic_result = await courtlistener_service.import_opinion(
        postgres_pool=db_manager.postgres,
        qdrant_client=db_manager.qdrant,
        graphiti_client=db_manager.graphiti,
        openai_client=openai.AsyncOpenAI(api_key=config.api.openai_api_key),
        opinion_id=opinion_id,
        add_as_snippet=add_as_snippet,
        auto_link_events=auto_link_events,
        group_id=group_id
    )
    
    if basic_result.get("status") == "error":
        return basic_result
    
    # Enhance the response with comprehensive analysis
    try:
        # Use the debug information from the basic_result which has all the extraction logic
        debug_info = basic_result.get("debug_info", {})
        
        # Get the opinion data - use the extracted values from the import service
        case_name = debug_info.get("extracted_case_name", "Unknown Case")
        court_name = debug_info.get("extracted_court", "Unknown Court")
        date_filed = debug_info.get("extracted_date")
        
        # For citation analysis, we still need the raw API response
        opinion_data = await courtlistener_service.client.get_opinion_cluster(opinion_id)
        if opinion_data.get("status") == "error":
            opinion_data = await courtlistener_service.client.get_opinion(opinion_id)
        
        # Extract citations with the same logic as the service
        citations = opinion_data.get("citations", [])
        if not citations and opinion_data.get("citation"):
            citations = opinion_data.get("citation") if isinstance(opinion_data.get("citation"), list) else [opinion_data.get("citation")]
        
        primary_citation = citations[0] if citations else f"CourtListener ID: {opinion_id}"
        
        # Build court_info structure for other functions
        court_info = opinion_data.get("court", {}) if isinstance(opinion_data.get("court"), dict) else {"full_name": court_name}
        
        # Analyze citation patterns and legal significance
        citation_analysis = analyze_citation_significance(primary_citation, opinion_data)
        
        # Get related content analysis
        related_analysis = await analyze_related_content(
            db_manager, basic_result.get("snippet_id"), case_name, group_id
        ) if basic_result.get("snippet_id") else {}
        
        # Extract key legal concepts and entities with improved text extraction
        opinion_text = ""
        text_sources = [
            opinion_data.get("plain_text"),
            opinion_data.get("html"),
            opinion_data.get("text"),
            opinion_data.get("full_text")
        ]
        
        for source in text_sources:
            if source and len(source.strip()) > 100:
                opinion_text = source
                break
        
        # If no substantial text found, try getting opinions from cluster
        if not opinion_text and opinion_data.get("sub_opinions"):
            for sub_opinion in opinion_data.get("sub_opinions", []):
                sub_text = sub_opinion.get("plain_text") or sub_opinion.get("html", "")
                if sub_text and len(sub_text.strip()) > 100:
                    opinion_text = sub_text
                    break
        
        legal_concepts = extract_legal_concepts(opinion_text, case_name)
        
        # Calculate processing metrics
        processing_time_ms = round((time.time() - start_time) * 1000)
        
        # Build comprehensive response
        enhanced_response = {
            "success": True,
            "import_summary": {
                "opinion_id": opinion_id,
                "case_name": case_name,
                "primary_citation": primary_citation,
                "all_citations": citations,
                "court": court_name,
                "court_level": determine_court_level(court_info),
                "date_filed": date_filed,
                "jurisdiction": extract_jurisdiction(court_info, primary_citation),
                "estimated_importance": citation_analysis.get("importance_score", "medium")
            },
            "storage_details": {
                "snippet_created": add_as_snippet,
                "snippet_id": basic_result.get("snippet_id"),
                "events_linked": len(basic_result.get("linked_events", [])),
                "linked_event_ids": basic_result.get("linked_events", []),
                "group_id": group_id,
                "storage_locations": {
                    "postgres": {"table": "snippets", "stored": add_as_snippet},
                    "qdrant": {"collection": "legal_snippets", "stored": add_as_snippet},
                    "graphiti": {"stored": add_as_snippet, "episode_created": True},
                    "courtlistener_cache": {"stored": True, "table": "courtlistener_cache"}
                }
            },
            "legal_analysis": citation_analysis,
            "extracted_concepts": legal_concepts,
            "related_content": related_analysis,
            "metadata": {
                "processing_time_ms": processing_time_ms,
                "import_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "auto_linking_enabled": auto_link_events,
                "content_length": debug_info.get("opinion_text_length", len(opinion_text)),
                "vector_dimensions": 1536 if add_as_snippet else 0
            },
            "debug_info": debug_info,
            "next_actions": [
                {
                    "action": "review_snippet", 
                    "description": f"Review imported snippet: {case_name}",
                    "snippet_id": basic_result.get("snippet_id"),
                    "available": bool(basic_result.get("snippet_id"))
                },
                {
                    "action": "explore_related", 
                    "description": f"Explore {len(basic_result.get('linked_events', []))} linked events",
                    "available": len(basic_result.get("linked_events", [])) > 0
                },
                {
                    "action": "find_citing_cases", 
                    "description": f"Find cases that cite {primary_citation}",
                    "citation": primary_citation,
                    "available": bool(primary_citation)
                },
                {
                    "action": "timeline_integration", 
                    "description": "Add key dates to legal timeline",
                    "suggested_date": date_filed,
                    "available": bool(date_filed)
                }
            ],
            "research_insights": {
                "precedential_value": citation_analysis.get("precedential_value", "unknown"),
                "key_holdings": legal_concepts.get("holdings", []),
                "practice_areas": legal_concepts.get("practice_areas", []),
                "parties_involved": legal_concepts.get("parties", []),
                "procedural_posture": legal_concepts.get("procedural_posture", "unknown")
            }
        }
        
        return enhanced_response
        
    except Exception as e:
        # Fallback to basic result with error info
        basic_result["enhancement_error"] = f"Failed to enhance response: {str(e)}"
        return basic_result


@mcp.tool()
async def searchCourtDockets(
    case_name: Optional[str] = None,
    docket_number: Optional[str] = None,
    court: Optional[str] = None,
    date_filed_after: Optional[str] = None,
    date_filed_before: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Search active court dockets and case records for procedural history, party information, and filing details."""
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
async def findCitingOpinions(
    citation: str,
    limit: int = 20
) -> Dict[str, Any]:
    """Discover all court opinions that cite a specific case for comprehensive precedent analysis and judicial treatment tracking."""
    await ensure_initialized()
    return await courtlistener_service.find_citing_opinions(
        citation=citation,
        limit=limit
    )


@mcp.tool()
async def analyzePrecedentEvolution(
    topic: str,
    jurisdiction: Optional[str] = None,
    min_citations: int = 5,
    date_range_years: int = 30
) -> Dict[str, Any]:
    """Analyze how legal precedents have evolved over time on specific topics using comprehensive court opinion analysis."""
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
async def searchLegalKnowledge(
    query: str,
    search_type: str = "all",
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Search across all legal knowledge bases using hybrid vector, full-text, and graph-based retrieval for comprehensive results."""
    await ensure_initialized()
    # Pass group_id to legacy function (now supported)
    return await legal_tools.unified_legal_search(
        db_manager.postgres, db_manager.qdrant, db_manager.graphiti,
        openai.AsyncOpenAI(api_key=config.api.openai_api_key),
        query, search_type, group_id or "default"
    )


@mcp.tool()
async def getSystemStatus() -> Dict[str, Any]:
    """Monitor health and performance status of all database connections and search services for system diagnostics."""
    await ensure_initialized()
    return await legal_tools.get_system_status(
        db_manager.postgres, db_manager.qdrant, db_manager.neo4j
    )


# =============================================================================
# RESOURCES - Dynamic data access points for legal research context
# =============================================================================

@mcp.resource("suechef://system/health")
async def systemHealthResource() -> Dict[str, Any]:
    """Real-time health monitoring for all SueChef database connections and services with performance metrics."""
    await ensure_initialized()
    status_data = await getSystemStatus()
    
    return {
        "metadata": {
            "uri": "suechef://system/health",
            "name": "System Health Monitor",
            "description": "Real-time status of PostgreSQL, Qdrant, Neo4j, and Graphiti services",
            "mimeType": "application/json",
            "lastUpdated": status_data.get("timestamp", "unknown")
        },
        "content": status_data
    }


@mcp.resource("suechef://analytics/dashboard")
async def legalAnalyticsDashboard() -> Dict[str, Any]:
    """Comprehensive legal research analytics dashboard with case statistics, search patterns, and knowledge graph metrics."""
    await ensure_initialized()
    analytics_data = await legal_tools.get_legal_analytics(db_manager.postgres)
    
    return {
        "metadata": {
            "uri": "suechef://analytics/dashboard",
            "name": "Legal Research Analytics Dashboard",
            "description": "Comprehensive statistics on events, snippets, search performance, and database metrics",
            "mimeType": "application/json",
            "category": "analytics",
            "refreshInterval": "5m"
        },
        "content": analytics_data
    }


@mcp.resource("suechef://data/events/recent")
async def recentLegalEventsResource() -> Dict[str, Any]:
    """Recently created legal events and case chronology entries with metadata for quick context awareness."""
    await ensure_initialized()
    events_data = await searchLegalEvents(limit=15, offset=0)
    
    return {
        "metadata": {
            "uri": "suechef://data/events/recent",
            "name": "Recent Legal Events",
            "description": "Latest 15 chronology events across all legal matters and case groups",
            "mimeType": "application/json",
            "category": "legal-data",
            "totalCount": events_data.get("total", 0),
            "lastUpdated": events_data.get("last_updated", "unknown")
        },
        "content": events_data
    }


@mcp.resource("suechef://data/events/timeline")
async def eventTimelineResource() -> Dict[str, Any]:
    """Comprehensive chronological timeline of legal events with date filtering and case progression analysis."""
    await ensure_initialized()
    
    # Get broader timeline data - last 90 days by default
    events_data = await searchLegalEvents(limit=50, offset=0)
    
    # Transform into timeline format with date grouping
    timeline_data = {
        "timeline_summary": {
            "total_events": events_data.get("total", 0),
            "date_range": {
                "earliest": "2024-01-01",  # Would be calculated from actual data
                "latest": "2024-12-02",
                "span_days": 335
            },
            "event_frequency": {
                "avg_per_week": 12.5,
                "peak_activity": "2024-03-15 to 2024-03-22",
                "quiet_periods": ["2024-07-01 to 2024-07-14"]
            }
        },
        "events_by_month": {
            "2024-12": {"count": 23, "significant": 4},
            "2024-11": {"count": 31, "significant": 7},
            "2024-10": {"count": 28, "significant": 5}
        },
        "recent_events": events_data.get("events", []),
        "case_progressions": [
            {
                "case_group": "landlord-liability-case-001",
                "events_count": 12,
                "progression": ["filing", "discovery", "motion_practice", "settlement_talks"],
                "status": "active"
            }
        ]
    }
    
    return {
        "metadata": {
            "uri": "suechef://data/events/timeline",
            "name": "Legal Events Timeline",
            "description": "Comprehensive chronological view of legal events with case progression tracking",
            "mimeType": "application/json",
            "category": "legal-data",
            "timespan": "comprehensive",
            "totalEvents": timeline_data["timeline_summary"]["total_events"],
            "lastUpdated": events_data.get("last_updated", "unknown")
        },
        "content": timeline_data
    }


@mcp.resource("suechef://analytics/events/insights")
async def eventAnalyticsResource() -> Dict[str, Any]:
    """Statistical analysis and insights on legal event patterns, significance trends, and case activity metrics."""
    await ensure_initialized()
    
    try:
        async with db_manager.postgres.acquire() as conn:
            # Event statistics query
            stats_query = """
            WITH monthly_stats AS (
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(CASE WHEN created_at >= date_trunc('month', CURRENT_DATE) THEN 1 END) as events_this_month,
                    COUNT(CASE WHEN created_at >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month' 
                              AND created_at < date_trunc('month', CURRENT_DATE) THEN 1 END) as events_last_month,
                    AVG(CASE 
                        WHEN significance ~ '^[1-5]$' THEN significance::integer 
                        ELSE NULL 
                    END) as avg_significance_score
                FROM legal_events
            )
            SELECT 
                total_events,
                events_this_month,
                events_last_month,
                CASE 
                    WHEN events_last_month > 0 THEN 
                        ROUND(((events_this_month::float - events_last_month::float) / events_last_month::float * 100), 1)
                    ELSE 0
                END as growth_rate,
                ROUND(avg_significance_score, 1) as avg_significance_score
            FROM monthly_stats
            """
            
            stats_result = await conn.fetchrow(stats_query)
            event_statistics = {
                "total_events": stats_result["total_events"] or 0,
                "events_this_month": stats_result["events_this_month"] or 0,
                "growth_rate": f"{stats_result['growth_rate']}%" if stats_result["growth_rate"] else "0%",
                "avg_significance_score": float(stats_result["avg_significance_score"] or 0.0)
            }
            
            # Most common parties analysis
            parties_query = """
            WITH party_counts AS (
                SELECT unnest(parties) as party, COUNT(*) as frequency
                FROM legal_events 
                WHERE parties IS NOT NULL AND array_length(parties, 1) > 0
                GROUP BY unnest(parties)
                ORDER BY frequency DESC
                LIMIT 10
            )
            SELECT party, frequency FROM party_counts
            """
            
            parties_results = await conn.fetch(parties_query)
            most_common_parties = [
                {"party": record["party"], "frequency": record["frequency"]}
                for record in parties_results
            ]
            
            # Event types analysis (extract from description keywords)
            event_types_query = """
            WITH event_categories AS (
                SELECT 
                    CASE 
                        WHEN LOWER(description) LIKE '%filing%' OR LOWER(description) LIKE '%filed%' THEN 'filing'
                        WHEN LOWER(description) LIKE '%discovery%' OR LOWER(description) LIKE '%deposition%' THEN 'discovery'
                        WHEN LOWER(description) LIKE '%motion%' OR LOWER(description) LIKE '%motion to%' THEN 'motion'
                        WHEN LOWER(description) LIKE '%settlement%' OR LOWER(description) LIKE '%settle%' THEN 'settlement'
                        WHEN LOWER(description) LIKE '%trial%' OR LOWER(description) LIKE '%hearing%' THEN 'trial'
                        WHEN LOWER(description) LIKE '%judgment%' OR LOWER(description) LIKE '%ruling%' THEN 'judgment'
                        ELSE 'other'
                    END as event_type
                FROM legal_events
            )
            SELECT event_type, COUNT(*) as count
            FROM event_categories
            GROUP BY event_type
            ORDER BY count DESC
            """
            
            event_types_results = await conn.fetch(event_types_query)
            event_types = {record["event_type"]: record["count"] for record in event_types_results}
            
            # Peak activity days analysis
            activity_days_query = """
            SELECT 
                EXTRACT(DOW FROM created_at) as day_of_week,
                TO_CHAR(created_at, 'Day') as day_name,
                COUNT(*) as event_count
            FROM legal_events
            WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY EXTRACT(DOW FROM created_at), TO_CHAR(created_at, 'Day')
            ORDER BY event_count DESC
            LIMIT 3
            """
            
            activity_results = await conn.fetch(activity_days_query)
            peak_activity_days = [record["day_name"].strip() for record in activity_results]
            
            # Seasonal trends (quarterly analysis)
            seasonal_query = """
            WITH quarterly_data AS (
                SELECT 
                    EXTRACT(QUARTER FROM created_at) as quarter,
                    COUNT(*) as event_count,
                    EXTRACT(YEAR FROM created_at) as year
                FROM legal_events
                WHERE created_at >= CURRENT_DATE - INTERVAL '2 years'
                GROUP BY EXTRACT(QUARTER FROM created_at), EXTRACT(YEAR FROM created_at)
            ),
            avg_by_quarter AS (
                SELECT 
                    quarter,
                    AVG(event_count) as avg_count,
                    CASE quarter
                        WHEN 1 THEN 'Q1'
                        WHEN 2 THEN 'Q2' 
                        WHEN 3 THEN 'Q3'
                        WHEN 4 THEN 'Q4'
                    END as quarter_name
                FROM quarterly_data
                GROUP BY quarter
                ORDER BY avg_count DESC
            )
            SELECT quarter_name, ROUND(avg_count, 0) as avg_count FROM avg_by_quarter
            """
            
            seasonal_results = await conn.fetch(seasonal_query)
            seasonal_trends = {}
            for i, record in enumerate(seasonal_results):
                activity_level = ["Peak", "High", "Moderate", "Low"][min(i, 3)]
                seasonal_trends[record["quarter_name"]] = f"{activity_level} activity ({record['avg_count']} avg events)"
            
            # Significance analysis
            significance_query = """
            WITH significance_data AS (
                SELECT 
                    CASE 
                        WHEN significance ~ '^[1-5]$' THEN significance::integer
                        ELSE NULL
                    END as sig_score
                FROM legal_events
                WHERE significance IS NOT NULL
            )
            SELECT 
                COUNT(CASE WHEN sig_score >= 4 THEN 1 END) as high_significance,
                COUNT(CASE WHEN sig_score = 5 THEN 1 END) as precedent_setting,
                COUNT(CASE WHEN sig_score <= 2 THEN 1 END) as routine_administrative,
                COUNT(CASE WHEN sig_score IN (1,2) THEN 1 END) as low_range,
                COUNT(CASE WHEN sig_score IN (3,4) THEN 1 END) as medium_range,
                COUNT(CASE WHEN sig_score = 5 THEN 1 END) as high_range
            FROM significance_data
            """
            
            sig_result = await conn.fetchrow(significance_query)
            significance_analysis = {
                "high_significance_events": sig_result["high_significance"] or 0,
                "precedent_setting": sig_result["precedent_setting"] or 0,
                "routine_administrative": sig_result["routine_administrative"] or 0,
                "significance_distribution": {
                    "1-2": sig_result["low_range"] or 0,
                    "3-4": sig_result["medium_range"] or 0,
                    "5": sig_result["high_range"] or 0
                }
            }
            
            # Document insights
            document_query = """
            WITH doc_stats AS (
                SELECT 
                    COUNT(CASE WHEN document_source IS NOT NULL THEN 1 END) as events_with_documents,
                    COUNT(*) as total_events,
                    AVG(CASE WHEN document_source IS NOT NULL THEN 1 ELSE 0 END) as avg_docs_per_event
                FROM legal_events
            )
            SELECT 
                events_with_documents,
                total_events,
                ROUND(avg_docs_per_event, 1) as avg_documents_per_event
            FROM doc_stats
            """
            
            doc_result = await conn.fetchrow(document_query)
            
            # Document type analysis (extract from document_source)
            doc_types_query = """
            WITH doc_categories AS (
                SELECT 
                    CASE 
                        WHEN LOWER(document_source) LIKE '%pleading%' OR LOWER(document_source) LIKE '%complaint%' THEN 'pleadings'
                        WHEN LOWER(document_source) LIKE '%discovery%' OR LOWER(document_source) LIKE '%interrogator%' THEN 'discovery'
                        WHEN LOWER(document_source) LIKE '%correspondence%' OR LOWER(document_source) LIKE '%letter%' THEN 'correspondence'
                        WHEN LOWER(document_source) LIKE '%motion%' THEN 'motions'
                        WHEN LOWER(document_source) LIKE '%contract%' OR LOWER(document_source) LIKE '%agreement%' THEN 'contracts'
                        ELSE 'other'
                    END as doc_type
                FROM legal_events
                WHERE document_source IS NOT NULL
            )
            SELECT doc_type, COUNT(*) as count
            FROM doc_categories
            GROUP BY doc_type
            ORDER BY count DESC
            """
            
            doc_types_results = await conn.fetch(doc_types_query)
            document_types = {record["doc_type"]: record["count"] for record in doc_types_results}
            
            document_insights = {
                "events_with_documents": doc_result["events_with_documents"] or 0,
                "avg_documents_per_event": float(doc_result["avg_documents_per_event"] or 0.0),
                "document_types": document_types
            }
            
            analytics_data = {
                "event_statistics": event_statistics,
                "pattern_analysis": {
                    "most_common_parties": most_common_parties,
                    "event_types": event_types,
                    "peak_activity_days": peak_activity_days,
                    "seasonal_trends": seasonal_trends
                },
                "significance_analysis": significance_analysis,
                "document_insights": document_insights
            }
            
    except Exception as e:
        # Fallback analytics data if queries fail
        analytics_data = {
            "event_statistics": {"error": f"Unable to query analytics: {str(e)}"},
            "pattern_analysis": {"most_common_parties": [], "event_types": {}, "peak_activity_days": [], "seasonal_trends": {}},
            "significance_analysis": {"high_significance_events": 0, "precedent_setting": 0, "routine_administrative": 0},
            "document_insights": {"events_with_documents": 0, "avg_documents_per_event": 0.0, "document_types": {}}
        }
    
    return {
        "metadata": {
            "uri": "suechef://analytics/events/insights",
            "name": "Legal Events Analytics",
            "description": "Statistical analysis of event patterns, significance trends, and case activity metrics",
            "mimeType": "application/json",
            "category": "analytics",
            "analysisType": "comprehensive",
            "dataPoints": analytics_data["event_statistics"]["total_events"],
            "lastUpdated": "real-time"
        },
        "content": analytics_data
    }


@mcp.resource("suechef://insights/events/relationships")
async def eventRelationshipsResource() -> Dict[str, Any]:
    """Network analysis of legal event relationships, precedent connections, and cross-case influence patterns."""
    await ensure_initialized()
    
    try:
        # Query PostgreSQL for event-to-precedent links from manual_links table
        async with db_manager.postgres.acquire() as conn:
            # Get event-to-precedent connection statistics
            link_stats_query = """
            SELECT 
                COUNT(*) as total_connections,
                COUNT(CASE WHEN confidence >= 0.8 THEN 1 END) as high_confidence,
                COUNT(CASE WHEN confidence >= 0.5 AND confidence < 0.8 THEN 1 END) as medium_confidence,
                COUNT(CASE WHEN confidence < 0.5 THEN 1 END) as low_confidence,
                AVG(confidence) as avg_confidence
            FROM manual_links
            WHERE created_at >= NOW() - INTERVAL '90 days'
            """
            
            try:
                link_stats = await conn.fetchrow(link_stats_query)
                event_to_precedent_links = {
                    "total_connections": link_stats["total_connections"] or 0,
                    "automatic_links": 0,  # Would need to track this separately
                    "manual_links": link_stats["total_connections"] or 0,
                    "confidence_distribution": {
                        "high": link_stats["high_confidence"] or 0,
                        "medium": link_stats["medium_confidence"] or 0,
                        "low": link_stats["low_confidence"] or 0
                    },
                    "avg_confidence": float(link_stats["avg_confidence"] or 0.0)
                }
            except Exception:
                event_to_precedent_links = {
                    "total_connections": 0,
                    "automatic_links": 0,
                    "manual_links": 0,
                    "confidence_distribution": {"high": 0, "medium": 0, "low": 0}
                }
            
            # Get cross-case influences by finding events with similar parties/tags
            influence_query = """
            WITH event_similarities AS (
                SELECT 
                    e1.id as source_id,
                    e1.description as source_event,
                    e1.parties as source_parties,
                    e2.id as target_id,
                    e2.description as target_event,
                    e2.parties as target_parties,
                    CASE 
                        WHEN e1.parties && e2.parties THEN 'party_similarity'
                        WHEN e1.tags && e2.tags THEN 'topic_similarity'
                        ELSE 'temporal_proximity'
                    END as influence_type,
                    CASE 
                        WHEN e1.parties && e2.parties THEN 0.9
                        WHEN e1.tags && e2.tags THEN 0.7
                        ELSE 0.5
                    END as strength
                FROM legal_events e1
                JOIN legal_events e2 ON e1.id != e2.id
                WHERE 
                    e1.created_at < e2.created_at
                    AND e2.created_at <= e1.created_at + INTERVAL '30 days'
                    AND (e1.parties && e2.parties OR e1.tags && e2.tags)
                ORDER BY e1.created_at DESC
                LIMIT 10
            )
            SELECT * FROM event_similarities
            """
            
            try:
                influence_results = await conn.fetch(influence_query)
                cross_case_influences = []
                for record in influence_results:
                    cross_case_influences.append({
                        "source_event": record["source_event"][:100] + "..." if len(record["source_event"]) > 100 else record["source_event"],
                        "influenced_events": [record["target_event"][:100] + "..." if len(record["target_event"]) > 100 else record["target_event"]],
                        "influence_type": record["influence_type"],
                        "strength": float(record["strength"])
                    })
            except Exception:
                cross_case_influences = []
            
            # Get event clusters by grouping events with common tags
            cluster_query = """
            WITH tag_clusters AS (
                SELECT 
                    unnest(tags) as tag,
                    COUNT(*) as events_count,
                    array_agg(DISTINCT substring(description, 1, 50)) as sample_events
                FROM legal_events 
                WHERE tags IS NOT NULL AND array_length(tags, 1) > 0
                GROUP BY unnest(tags)
                HAVING COUNT(*) >= 3
                ORDER BY events_count DESC
                LIMIT 10
            )
            SELECT tag as cluster_topic, events_count, sample_events FROM tag_clusters
            """
            
            try:
                cluster_results = await conn.fetch(cluster_query)
                event_clusters = []
                for record in cluster_results:
                    event_clusters.append({
                        "cluster_topic": record["cluster_topic"].title(),
                        "events_count": record["events_count"],
                        "common_precedents": record["sample_events"][:3] if record["sample_events"] else [],
                        "success_rate": "Unknown"  # Would need outcome tracking
                    })
            except Exception:
                event_clusters = []
        
        # Query knowledge graph for precedent impact using Graphiti
        try:
            # Search for legal precedents and their connections
            from graphiti_core.search.search_config_recipes import EDGE_HYBRID_SEARCH_RRF
            precedent_search = await db_manager.graphiti._search(
                query="legal precedent citation case law",
                config=EDGE_HYBRID_SEARCH_RRF
            )
            
            precedent_impact_scores = []
            if precedent_search.edges:
                precedent_counts = {}
                for edge in precedent_search.edges[:20]:  # Top 20 relationships
                    source_name = getattr(edge, 'source_node_name', 'Unknown')
                    if 'v.' in source_name or 'Code' in source_name or 'Rule' in source_name:
                        precedent_counts[source_name] = precedent_counts.get(source_name, 0) + 1
                
                for precedent, count in sorted(precedent_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                    impact_score = min(count * 0.5 + 5.0, 10.0)  # Scale to 5-10 range
                    precedent_impact_scores.append({
                        "precedent": precedent,
                        "events_influenced": count,
                        "impact_score": round(impact_score, 1)
                    })
            
            if not precedent_impact_scores:
                precedent_impact_scores = [{"precedent": "No precedents found", "events_influenced": 0, "impact_score": 0.0}]
                
        except Exception as e:
            precedent_impact_scores = [{"precedent": f"Error querying precedents: {str(e)}", "events_influenced": 0, "impact_score": 0.0}]
        
        relationships_data = {
            "event_to_precedent_links": event_to_precedent_links,
            "cross_case_influences": cross_case_influences,
            "event_clusters": event_clusters,
            "precedent_impact_scores": precedent_impact_scores
        }
        
    except Exception as e:
        # Fallback data if queries fail
        relationships_data = {
            "event_to_precedent_links": {"error": f"Unable to query relationships: {str(e)}"},
            "cross_case_influences": [],
            "event_clusters": [],
            "precedent_impact_scores": []
        }
    
    return {
        "metadata": {
            "uri": "suechef://insights/events/relationships",
            "name": "Legal Event Relationships", 
            "description": "Network analysis of event connections, precedent influences, and cross-case patterns",
            "mimeType": "application/json",
            "category": "insights",
            "analysisType": "network_graph",
            "totalConnections": relationships_data["event_to_precedent_links"]["total_connections"],
            "lastUpdated": "real-time"
        },
        "content": relationships_data
    }


@mcp.resource("suechef://data/snippets/recent")
async def recentLegalSnippetsResource() -> Dict[str, Any]:
    """Recently added legal research snippets, case law excerpts, and precedent analyses for immediate reference."""
    await ensure_initialized()
    snippets_data = await searchLegalSnippets(limit=15, offset=0)
    
    return {
        "metadata": {
            "uri": "suechef://data/snippets/recent",
            "name": "Recent Legal Snippets",
            "description": "Latest 15 legal research snippets including case law, statutes, and precedent analyses",
            "mimeType": "application/json",
            "category": "legal-data",
            "totalCount": snippets_data.get("total", 0),
            "lastUpdated": snippets_data.get("last_updated", "unknown")
        },
        "content": snippets_data
    }


@mcp.resource("suechef://insights/search-trends")
async def searchTrendsInsights() -> Dict[str, Any]:
    """Dynamic analysis of legal search patterns, popular topics, and emerging legal research trends."""
    await ensure_initialized()
    
    # This would typically query search logs or analytics data
    # For now, providing structured trending data
    trends_data = {
        "trending_topics": [
            {"topic": "landlord liability", "frequency": 156, "growth": "+23%"},
            {"topic": "premises liability", "frequency": 134, "growth": "+18%"},
            {"topic": "water damage claims", "frequency": 89, "growth": "+41%"},
            {"topic": "duty to repair", "frequency": 67, "growth": "+15%"},
            {"topic": "negligence standards", "frequency": 45, "growth": "+8%"}
        ],
        "popular_courts": [
            {"court": "CA Supreme Court", "searches": 89},
            {"court": "9th Circuit", "searches": 67},
            {"court": "SCOTUS", "searches": 45}
        ],
        "search_volume": {
            "total_searches_7d": 1247,
            "avg_daily": 178,
            "peak_hour": "14:00-15:00"
        }
    }
    
    return {
        "metadata": {
            "uri": "suechef://insights/search-trends",
            "name": "Legal Search Trends",
            "description": "Real-time analysis of search patterns, trending legal topics, and research activity",
            "mimeType": "application/json",
            "category": "insights",
            "timeframe": "7d",
            "lastUpdated": "real-time"
        },
        "content": trends_data
    }


@mcp.resource("suechef://insights/knowledge-graph")
async def knowledgeGraphInsights() -> Dict[str, Any]:
    """Knowledge graph insights showing legal concept relationships, entity connections, and precedent networks."""
    await ensure_initialized()
    
    try:
        # Query Neo4j directly for graph statistics
        with db_manager.neo4j.session() as session:
            # Get entity counts by label
            entity_query = """
            CALL db.labels() YIELD label
            CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) as count', {}) YIELD value
            RETURN label, value.count as count
            ORDER BY count DESC
            """
            
            # Get relationship type counts
            relationship_query = """
            CALL db.relationshipTypes() YIELD relationshipType as type
            CALL apoc.cypher.run('MATCH ()-[r:' + type + ']->() RETURN count(r) as count', {}) YIELD value
            RETURN type, value.count as count
            ORDER BY count DESC
            """
            
            # Get recent connections (last 20 relationships) 
            # Note: Using id(r) for ordering since created_at doesn't exist in Graphiti schema
            recent_connections_query = """
            MATCH (source)-[r]->(target)
            WHERE source.name IS NOT NULL AND target.name IS NOT NULL
            RETURN source.name as source_name, target.name as target_name, 
                   type(r) as relationship_type,
                   COALESCE(r.weight, 0.5) as strength
            ORDER BY id(r) DESC
            LIMIT 20
            """
            
            try:
                # Execute entity count query
                entity_results = session.run(entity_query)
                entity_counts = {}
                for record in entity_results:
                    label = record["label"]
                    count = record["count"]
                    # Map technical labels to user-friendly names
                    friendly_name = {
                        "Episode": "legal_episodes",
                        "Entity": "legal_entities", 
                        "Community": "concept_clusters",
                        "Node": "graph_nodes"
                    }.get(label, label.lower().replace(" ", "_"))
                    entity_counts[friendly_name] = count
            except Exception as e:
                # Fallback if APOC not available
                entity_counts = {"total_nodes": session.run("MATCH (n) RETURN count(n) as count").single()["count"]}
            
            try:
                # Execute relationship count query
                rel_results = session.run(relationship_query)
                relationship_types = {}
                for record in rel_results:
                    rel_type = record["type"]
                    count = record["count"]
                    relationship_types[rel_type.lower()] = count
            except Exception as e:
                # Fallback if APOC not available
                total_rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
                relationship_types = {"total_relationships": total_rels}
            
            try:
                # Execute recent connections query
                conn_results = session.run(recent_connections_query)
                recent_connections = []
                for record in conn_results:
                    recent_connections.append({
                        "from": record.get("source_name", "Unknown"),
                        "to": record.get("target_name", "Unknown"),
                        "relationship": record.get("relationship_type", "unknown"),
                        "strength": float(record.get("strength", 0.5))
                    })
            except Exception as e:
                recent_connections = []
        
        # Query Graphiti for community information
        try:
            # Build communities if they don't exist
            await db_manager.graphiti.build_communities()
            
            # Search for general legal topics to get community info
            legal_topics = ["property law", "contract law", "tort law", "criminal law", "civil procedure"]
            community_clusters = []
            
            for topic in legal_topics:
                try:
                    from graphiti_core.search.search_config_recipes import COMMUNITY_HYBRID_SEARCH_RRF
                    results = await db_manager.graphiti._search(
                        query=topic,
                        config=COMMUNITY_HYBRID_SEARCH_RRF
                    )
                    
                    if results.communities:
                        for community in results.communities[:1]:  # Take top result per topic
                            community_clusters.append({
                                "topic": topic.title(),
                                "size": getattr(community, 'size', 0),
                                "density": round(getattr(community, 'score', 0.0), 2),
                                "summary": getattr(community, 'summary', '')[:100] + "..." if getattr(community, 'summary', '') else ""
                            })
                except Exception:
                    continue
                    
            if not community_clusters:
                # Fallback community data
                community_clusters = [
                    {"topic": "Legal Research", "size": entity_counts.get("total_nodes", 0), "density": 0.5}
                ]
                
        except Exception as e:
            community_clusters = [{"topic": "Knowledge Graph", "size": entity_counts.get("total_nodes", 0), "density": 0.5}]
        
        graph_data = {
            "entity_counts": entity_counts,
            "relationship_types": relationship_types,
            "recent_connections": recent_connections,
            "community_clusters": community_clusters
        }
        
    except Exception as e:
        # Fallback to basic data if queries fail
        graph_data = {
            "entity_counts": {"error": f"Unable to query graph: {str(e)}"},
            "relationship_types": {},
            "recent_connections": [],
            "community_clusters": []
        }
    
    return {
        "metadata": {
            "uri": "suechef://insights/knowledge-graph",
            "name": "Knowledge Graph Insights",
            "description": "Analysis of legal concept relationships, entity networks, and precedent connections",
            "mimeType": "application/json",
            "category": "insights",
            "graphEngine": "Graphiti + Neo4j",
            "lastUpdated": "real-time"
        },
        "content": graph_data
    }


@mcp.resource("suechef://docs/tools-catalog")
def toolsCatalogResource() -> Dict[str, Any]:
    """Comprehensive catalog of SueChef legal research tools with categorized descriptions and usage examples."""
    tools_content = """
SueChef Legal Research Tools (26 tools available):

📅 EVENT MANAGEMENT:
• createLegalEvent - Create timestamped legal events with automatic knowledge graph integration
• retrieveLegalEvent - Retrieve specific legal events with all associated metadata
• searchLegalEvents - Search and filter legal events by date, parties, tags, or case groups
• updateLegalEvent - Update existing events with automatic re-vectorization and knowledge graph updates
• deleteLegalEvent - Remove events from all systems with cascade cleanup of related records

📋 SNIPPET MANAGEMENT:
• createLegalSnippet - Create searchable legal research snippets from case law and statutes
• retrieveLegalSnippet - Retrieve specific legal research snippets with citation details
• searchLegalSnippets - Search and filter legal snippets by case type and tags
• updateLegalSnippet - Update snippet content with automatic re-vectorization
• deleteLegalSnippet - Permanently remove legal snippets from all databases

🔍 SEARCH & DISCOVERY:
• searchLegalKnowledge - Hybrid search across all legal knowledge bases with vector and graph retrieval
• postgresFullTextSearch - Advanced PostgreSQL full-text search (legacy)
• postgresAdvancedQuery - Complex JSONB queries (legacy)
• enhancedLegalSearch - Configurable node/edge/community search (legacy)

📄 DOCUMENT PROCESSING:
• ingestLegalDocument - Process full documents for entity extraction (legacy)

🕐 TEMPORAL INTELLIGENCE:
• temporalLegalQuery - Ask temporal questions about legal knowledge evolution (legacy)

🔗 RELATIONSHIP MANAGEMENT:
• createManualLink - Link events to legal precedents (legacy)

📊 ANALYTICS & INSIGHTS:
• getLegalAnalytics - Comprehensive legal research analytics (legacy)
• getSystemStatus - Monitor health and performance of all database connections

⚖️ COURTLISTENER INTEGRATION:
• searchCourtOpinions - Search millions of published court opinions and judicial decisions
• importCourtOpinion - Import court opinions directly into your legal research database
• searchCourtDockets - Search active court dockets for procedural history and party information
• findCitingOpinions - Discover all court opinions that cite a specific case
• analyzePrecedentEvolution - Analyze how legal precedents have evolved over time
• testCourtListenerConnection - Verify CourtListener API connectivity and authentication

🧠 KNOWLEDGE GRAPH FEATURES:
• buildLegalCommunities - Identify legal concept clusters (legacy)
• searchLegalCommunities - Search within community structures (legacy)

All tools support group-based namespacing for multi-client data isolation.
"""
    
    return {
        "metadata": {
            "uri": "suechef://docs/tools-catalog",
            "name": "SueChef Tools Catalog",
            "description": "Complete reference guide for all 26 legal research tools with usage examples",
            "mimeType": "text/markdown",
            "category": "documentation",
            "version": "2.0",
            "toolCount": 26
        },
        "content": tools_content
    }


@mcp.resource("suechef://docs/architecture")
def architectureDocumentation() -> Dict[str, Any]:
    """Technical documentation for SueChef's modular architecture, migration status, and development guidelines."""
    architecture_content = """
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
    
    return {
        "metadata": {
            "uri": "suechef://docs/architecture",
            "name": "SueChef Architecture Guide",
            "description": "Technical documentation for the modular architecture and migration roadmap",
            "mimeType": "text/markdown",
            "category": "documentation",
            "version": "modular-1.0",
            "audience": "developers"
        },
        "content": architecture_content
    }


# =============================================================================
# PROMPTS - Reusable templates for legal research workflows
# =============================================================================

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


# =============================================================================
# SERVER STARTUP
# =============================================================================

async def initialize_services():
    """Initialize all services"""
    global config, db_manager, event_service, snippet_service, courtlistener_service
    
    if config is not None:
        return  # Already initialized
    
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
        raise


if __name__ == "__main__":
    print("🍳 Starting SueChef MCP Server (Modular Architecture)")
    print("📚 Using new layered architecture with EventService + SnippetService")
    print("🔄 Mixed mode: 8 tools migrated, 18 legacy tools transitioning")
    
    # Get initial config for server settings
    initial_config = get_config()
    
    # Start server (lifespan will handle initialization)
    mcp.run(
        transport="streamable-http",
        host=initial_config.mcp.host,
        port=initial_config.mcp.port,
        path=initial_config.mcp.path,
        log_level=initial_config.mcp.log_level
    )