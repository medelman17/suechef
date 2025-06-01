"""
CourtListener API Integration for Legal Research MCP Server

This module wraps CourtListener's API v4 functionality and integrates it
with the existing PostgreSQL + Qdrant + Graphiti architecture.
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import json
from urllib.parse import urlencode, quote
import os
import asyncpg
from qdrant_client import QdrantClient
from graphiti_core import Graphiti
import openai

# Import existing tools
import legal_tools

# CourtListener API configuration
COURTLISTENER_API_BASE = "https://www.courtlistener.com/api/rest/v4"
COURTLISTENER_API_KEY = os.getenv("COURTLISTENER_API_KEY", "")


class AsyncCourtListenerClient:
    """Async client for interacting with CourtListener API v4"""
    
    def __init__(self, api_key: str = COURTLISTENER_API_KEY):
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Token {api_key}"
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to CourtListener API"""
        url = f"{COURTLISTENER_API_BASE}/{endpoint}"
        if not url.endswith('/'):
            url += '/'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=self.headers) as response:
                response.raise_for_status()
                return await response.json()
    
    async def search_opinions(self, query: str, **kwargs) -> Dict:
        """Search court opinions"""
        params = {"q": query, **kwargs}
        return await self._make_request("search", params)
    
    async def get_opinion(self, opinion_id: int) -> Dict:
        """Get specific opinion by ID"""
        return await self._make_request(f"opinions/{opinion_id}")
    
    async def search_dockets(self, query: str, **kwargs) -> Dict:
        """Search court dockets"""
        params = {"q": query, "type": "d", **kwargs}
        return await self._make_request("search", params)
    
    async def get_docket(self, docket_id: int) -> Dict:
        """Get specific docket by ID"""
        return await self._make_request(f"dockets/{docket_id}")
    
    async def get_court(self, court_id: str) -> Dict:
        """Get court information"""
        return await self._make_request(f"courts/{court_id}")
    
    async def search_people(self, name: str, **kwargs) -> Dict:
        """Search for judges, attorneys, parties"""
        params = {"name": name, **kwargs}
        return await self._make_request("people", params)


# Initialize client
cl_client = AsyncCourtListenerClient()


async def search_courtlistener_opinions(
    query: str,
    court: Optional[str] = None,
    date_after: Optional[str] = None,
    date_before: Optional[str] = None,
    cited_gt: Optional[int] = None,  # Minimum citation count
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search CourtListener for court opinions matching query.
    
    Args:
        query: Search terms (e.g., "landlord tenant water damage")
        court: Court abbreviation (e.g., "scotus", "ca9")
        date_after: Filter opinions after this date (YYYY-MM-DD)
        date_before: Filter opinions before this date
        cited_gt: Minimum number of times opinion has been cited
        limit: Maximum results to return
    """
    params = {
        "order_by": "-score",
        "per_page": limit
    }
    
    if court:
        params["court"] = court
    if date_after:
        params["filed_after"] = date_after
    if date_before:
        params["filed_before"] = date_before
    if cited_gt:
        params["cited_gt"] = cited_gt
    
    try:
        results = await cl_client.search_opinions(query, **params)
        
        # Process results for integration
        processed_results = []
        for result in results.get("results", []):
            processed_results.append({
                "id": result.get("id"),
                "case_name": result.get("caseName"),
                "court": result.get("court"),
                "date_filed": result.get("dateFiled"),
                "citation": result.get("citation", [""])[0] if result.get("citation") else "",
                "snippet": result.get("snippet", ""),
                "absolute_url": f"https://www.courtlistener.com{result.get('absolute_url', '')}",
                "citation_count": result.get("citeCount", 0),
                "cluster_id": result.get("cluster_id")
            })
        
        return {
            "status": "success",
            "count": results.get("count", 0),
            "results": processed_results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def import_courtlistener_opinion(
    postgres_pool: asyncpg.Pool,
    qdrant_client: QdrantClient,
    graphiti_client: Graphiti,
    openai_client,
    opinion_id: int,
    add_as_snippet: bool = True,
    auto_link_events: bool = True
) -> Dict[str, Any]:
    """
    Import a CourtListener opinion into your legal research system.
    
    Args:
        opinion_id: CourtListener opinion ID
        add_as_snippet: Create a snippet in your local system
        auto_link_events: Attempt to link with existing chronology events
    """
    try:
        # Fetch full opinion data
        opinion = await cl_client.get_opinion(opinion_id)
        
        result = {"opinion_id": opinion_id}
        
        # Create snippet if requested
        if add_as_snippet:
            # Extract key information
            case_name = opinion.get("case_name", "Unknown Case")
            citations = opinion.get("citations", [])
            citation_string = citations[0] if citations else f"Opinion ID: {opinion_id}"
            
            # Get the opinion text (may need additional API call for full text)
            opinion_text = opinion.get("plain_text", opinion.get("html", ""))
            key_excerpt = opinion_text[:500] + "..." if len(opinion_text) > 500 else opinion_text
            
            # Determine tags based on content
            tags = []
            if "landlord" in opinion_text.lower():
                tags.append("landlord-tenant")
            if "water" in opinion_text.lower() or "leak" in opinion_text.lower():
                tags.append("water-damage")
            if "negligence" in opinion_text.lower():
                tags.append("negligence")
            tags.append("courtlistener-import")
            
            # Add to your snippet system
            snippet_result = await legal_tools.create_snippet(
                postgres_pool=postgres_pool,
                qdrant_client=qdrant_client,
                graphiti_client=graphiti_client,
                openai_client=openai_client,
                citation=f"{case_name}, {citation_string}",
                key_language=key_excerpt,
                tags=tags,
                context=f"CourtListener ID: {opinion_id}",
                case_type=opinion.get("type", "civil")
            )
            result["snippet_id"] = snippet_result.get("snippet_id")
        
        # Auto-link to events if requested
        if auto_link_events and add_as_snippet and result.get("snippet_id"):
            # Search for related events using semantic search
            search_results = await legal_tools.unified_legal_search(
                postgres_pool=postgres_pool,
                qdrant_client=qdrant_client,
                graphiti_client=graphiti_client,
                openai_client=openai_client,
                query=f"{case_name} {' '.join(tags)}",
                search_type="vector"
            )
            
            # Link to most relevant events
            linked_events = []
            vector_results = search_results.get("vector", {}).get("events", [])
            for event in vector_results[:3]:
                if event.get("score", 0) > 0.7:
                    link_result = await legal_tools.create_manual_link(
                        postgres_pool=postgres_pool,
                        event_id=event["id"],
                        snippet_id=result["snippet_id"],
                        relationship_type="supports",
                        confidence=event.get("score", 0.8),
                        notes=f"Auto-linked from CourtListener import"
                    )
                    linked_events.append(event["id"])
            
            result["linked_events"] = linked_events
        
        # Store reference to CourtListener in PostgreSQL
        async with postgres_pool.acquire() as conn:
            await conn.execute(
                '''
                INSERT INTO courtlistener_cache 
                (courtlistener_id, opinion_data, imported_at, local_snippet_id)
                VALUES ($1, $2, NOW(), $3)
                ON CONFLICT (courtlistener_id) DO UPDATE
                SET opinion_data = EXCLUDED.opinion_data,
                    imported_at = NOW()
                ''',
                opinion_id,
                json.dumps(opinion),
                result.get("snippet_id")
            )
        
        result["status"] = "success"
        return result
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def search_courtlistener_dockets(
    case_name: Optional[str] = None,
    docket_number: Optional[str] = None,
    court: Optional[str] = None,
    date_filed_after: Optional[str] = None,
    date_filed_before: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search CourtListener dockets (active cases).
    
    Useful for finding:
    - Active litigation similar to yours
    - Procedural history of cases
    - Party and attorney information
    """
    query_parts = []
    if case_name:
        query_parts.append(f'case_name:"{case_name}"')
    if docket_number:
        query_parts.append(f'docket_number:"{docket_number}"')
    
    query = " AND ".join(query_parts) if query_parts else "*"
    
    params = {
        "type": "d",
        "order_by": "-score",
        "per_page": limit
    }
    
    if court:
        params["court"] = court
    if date_filed_after:
        params["date_filed__gte"] = date_filed_after
    if date_filed_before:
        params["date_filed__lte"] = date_filed_before
    
    try:
        results = await cl_client.search_dockets(query, **params)
        
        processed_results = []
        for result in results.get("results", []):
            processed_results.append({
                "id": result.get("id"),
                "case_name": result.get("case_name"),
                "docket_number": result.get("docket_number"),
                "court": result.get("court"),
                "date_filed": result.get("date_filed"),
                "date_terminated": result.get("date_terminated"),
                "nature_of_suit": result.get("nature_of_suit"),
                "absolute_url": f"https://www.courtlistener.com{result.get('absolute_url', '')}",
                "party_info": result.get("party_info", [])
            })
        
        return {
            "status": "success",
            "count": results.get("count", 0),
            "results": processed_results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def find_citing_opinions(
    citation: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Find all opinions that cite a specific case.
    
    Useful for:
    - Checking if a precedent is still good law
    - Finding similar cases that relied on the same precedent
    - Building a citation network
    """
    try:
        # Search for opinions citing this case
        results = await cl_client.search_opinions(
            f'cites:"{citation}"',
            order_by="-score",
            per_page=limit
        )
        
        return {
            "status": "success",
            "cited_case": citation,
            "citing_count": results.get("count", 0),
            "citing_opinions": [
                {
                    "case_name": r.get("caseName"),
                    "citation": r.get("citation", [""])[0] if r.get("citation") else "",
                    "date": r.get("dateFiled"),
                    "court": r.get("court"),
                    "snippet": r.get("snippet", "")
                }
                for r in results.get("results", [])
            ]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def analyze_courtlistener_precedents(
    topic: str,
    jurisdiction: Optional[str] = None,
    min_citations: int = 5,
    date_range_years: int = 30
) -> Dict[str, Any]:
    """
    Analyze precedent evolution on a topic using CourtListener data.
    
    This tool:
    1. Searches for relevant opinions
    2. Identifies the most-cited cases
    3. Tracks how the law has evolved
    4. Integrates with your chronology
    """
    end_date = datetime.now().date()
    start_date = date(end_date.year - date_range_years, end_date.month, end_date.day)
    
    try:
        # Search for opinions on this topic
        results = await cl_client.search_opinions(
            topic,
            court=jurisdiction,
            filed_after=str(start_date),
            filed_before=str(end_date),
            cited_gt=min_citations,
            order_by="-citeCount",
            per_page=50
        )
        
        # Group by time periods
        periods = {}
        for opinion in results.get("results", []):
            date_filed = opinion.get("dateFiled")
            if date_filed:
                year = int(date_filed[:4])
                decade = f"{(year // 10) * 10}s"
                if decade not in periods:
                    periods[decade] = []
                periods[decade].append({
                    "case_name": opinion.get("caseName"),
                    "year": year,
                    "citations": opinion.get("citeCount", 0),
                    "snippet": opinion.get("snippet", ""),
                    "id": opinion.get("id")
                })
        
        # Find seminal cases (most cited)
        seminal_cases = sorted(
            results.get("results", []),
            key=lambda x: x.get("citeCount", 0),
            reverse=True
        )[:5]
        
        # Generate analysis
        analysis = {
            "topic": topic,
            "jurisdiction": jurisdiction or "all federal and state courts",
            "time_period": f"{start_date.year}-{end_date.year}",
            "total_relevant_cases": results.get("count", 0),
            "evolution_by_decade": periods,
            "seminal_cases": [
                {
                    "case_name": c.get("caseName"),
                    "citations": c.get("citeCount", 0),
                    "year": c.get("dateFiled", "")[:4] if c.get("dateFiled") else "Unknown",
                    "holding": c.get("snippet", "")[:200] + "..." if c.get("snippet") else ""
                }
                for c in seminal_cases
            ],
            "trend": _analyze_legal_trend(periods)
        }
        
        return {
            "status": "success",
            "analysis": analysis
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _analyze_legal_trend(periods: Dict) -> str:
    """Analyze how legal precedent has evolved over time"""
    if not periods:
        return "Insufficient data for trend analysis"
    
    sorted_decades = sorted(periods.keys())
    if len(sorted_decades) < 2:
        return "Limited time range for trend analysis"
    
    # Compare case counts and citations
    early_period = sorted_decades[0]
    recent_period = sorted_decades[-1]
    
    early_count = len(periods[early_period])
    recent_count = len(periods[recent_period])
    
    if recent_count > early_count * 1.5:
        trend = "Significantly increasing litigation"
    elif recent_count > early_count:
        trend = "Moderately increasing litigation"
    elif recent_count < early_count * 0.7:
        trend = "Decreasing litigation"
    else:
        trend = "Stable litigation levels"
    
    return f"{trend} from {early_period} ({early_count} cases) to {recent_period} ({recent_count} cases)"