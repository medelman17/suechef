"""
CourtListener API Integration Service

This service wraps CourtListener's API v4 functionality and integrates it
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
import logging

from src.config.settings import SueChefConfig

logger = logging.getLogger(__name__)


class AsyncCourtListenerClient:
    """Async client for interacting with CourtListener API v4"""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip() if api_key else ""
        self.api_base = "https://www.courtlistener.com/api/rest/v4"
        self.headers = {
            "User-Agent": "SueChef Legal Research MCP/1.0",
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            self.headers["Authorization"] = f"Token {self.api_key}"
            logger.info("CourtListener API client initialized with authentication")
        else:
            logger.warning("CourtListener API key not configured. Some functionality may be limited.")
    
    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to CourtListener API"""
        if not self.api_key and endpoint in ["search", "opinions", "dockets"]:
            return {
                "status": "error", 
                "message": "CourtListener API key required. Set COURTLISTENER_API_KEY environment variable.",
                "fix": "Get API key from https://www.courtlistener.com/help/api/rest/ and set COURTLISTENER_API_KEY"
            }
        
        url = f"{self.api_base}/{endpoint}"
        if not url.endswith('/'):
            url += '/'
        
        if params:
            params = {k: v for k, v in params.items() if v is not None}
        
        logger.debug(f"CourtListener API request: {url} with params: {params}")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(url, params=params, headers=self.headers) as response:
                    response_text = await response.text()
                    
                    if response.status == 400:
                        logger.error(f"CourtListener 400 Error: {response_text}")
                        return {
                            "status": "error",
                            "message": f"Bad Request (400): {response_text}. Check API parameters and authentication.",
                            "url": str(response.url),
                            "params": params
                        }
                    elif response.status == 401:
                        return {
                            "status": "error",
                            "message": "Unauthorized (401): Invalid or missing API key",
                            "fix": "Check your COURTLISTENER_API_KEY environment variable"
                        }
                    elif response.status == 403:
                        return {
                            "status": "error", 
                            "message": "Forbidden (403): API key lacks required permissions",
                            "fix": "Verify your CourtListener API key has proper permissions"
                        }
                    elif response.status == 429:
                        return {
                            "status": "error",
                            "message": "Rate limited (429): Too many requests. Please wait before retrying."
                        }
                    
                    response.raise_for_status()
                    return await response.json()
                    
        except aiohttp.ClientError as e:
            logger.error(f"CourtListener API request failed: {str(e)}")
            return {"status": "error", "message": f"Request failed: {str(e)}"}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from CourtListener: {response_text}")
            return {"status": "error", "message": f"Invalid JSON response: {str(e)}"}
    
    async def search_opinions(self, query: str, **kwargs) -> Dict:
        """Search court opinions"""
        params = {"q": query, **kwargs}
        return await self._make_request("search", params)
    
    async def get_opinion(self, opinion_id: int) -> Dict:
        """Get specific opinion by ID"""
        return await self._make_request(f"opinions/{opinion_id}")
    
    async def get_opinion_cluster(self, cluster_id: int) -> Dict:
        """Get opinion cluster (case) by ID - this is what search results return"""
        return await self._make_request(f"opinion-clusters/{cluster_id}")
    
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


class CourtListenerService:
    """Service for CourtListener API integration"""
    
    def __init__(self, config: SueChefConfig):
        self.config = config
        self.api_key = os.getenv("COURTLISTENER_API_KEY", "")
        self.client = AsyncCourtListenerClient(self.api_key)
        logger.info("CourtListenerService initialized")
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test CourtListener API connection and authentication"""
        
        # Test 1: Check API key configuration
        if not self.api_key:
            return {
                "status": "error",
                "message": "COURTLISTENER_API_KEY environment variable not set",
                "fix": "Set COURTLISTENER_API_KEY in your .env file",
                "steps": [
                    "1. Get API key from https://www.courtlistener.com/help/api/rest/",
                    "2. Add COURTLISTENER_API_KEY=your_key to .env file",
                    "3. Restart the service: docker-compose restart suechef"
                ]
            }
        
        # Test 2: Test basic API connectivity with courts endpoint (usually public)
        try:
            result = await self.client._make_request("courts")
            if result.get("status") == "error":
                return {
                    "status": "error", 
                    "message": f"API connection failed: {result.get('message')}",
                    "api_key_configured": bool(self.api_key),
                    "details": result
                }
            
            # Test 3: Test search endpoint with minimal query
            search_result = await self.client.search_opinions("test", per_page=1)
            
            if search_result.get("status") == "error":
                return {
                    "status": "error",
                    "message": f"Search endpoint failed: {search_result.get('message')}",
                    "api_key_configured": True,
                    "courts_endpoint": "OK",
                    "search_endpoint": "FAILED",
                    "details": search_result
                }
            
            return {
                "status": "success",
                "message": "CourtListener API connection successful",
                "api_key_configured": True,
                "courts_endpoint": "OK",
                "search_endpoint": "OK",
                "test_search_count": search_result.get("count", 0)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}",
                "api_key_configured": bool(self.api_key)
            }
    
    async def search_opinions(
        self,
        query: str,
        court: Optional[str] = None,
        date_after: Optional[str] = None,
        date_before: Optional[str] = None,
        cited_gt: Optional[int] = None,
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
        if not query or not query.strip():
            return {"status": "error", "message": "Query parameter is required"}
        
        params = {
            "per_page": min(limit, 100)
        }
        
        if court:
            params["court"] = court
        if date_after:
            params["filed_after"] = date_after  
        if date_before:
            params["filed_before"] = date_before
        if cited_gt and cited_gt > 0:
            params["cited_gt"] = cited_gt
        
        try:
            result = await self.client.search_opinions(query.strip(), **params)
            
            if result.get("status") == "error":
                return result
            
            processed_results = []
            for item in result.get("results", []):
                # Extract opinion ID from cluster_id or absolute_url
                opinion_id = item.get("cluster_id")
                if not opinion_id and item.get("absolute_url"):
                    # Extract ID from URL like "/opinion/7404835/myska-v-new-jersey/"
                    url_parts = item.get("absolute_url", "").split("/")
                    for part in url_parts:
                        if part.isdigit():
                            opinion_id = int(part)
                            break
                
                processed_results.append({
                    "id": opinion_id,  # Use cluster_id as the opinion ID
                    "case_name": item.get("caseName") or item.get("case_name"),
                    "court": item.get("court"),
                    "date_filed": item.get("dateFiled") or item.get("date_filed"),
                    "citation": item.get("citation", [""])[0] if item.get("citation") else "",
                    "snippet": item.get("snippet", ""),
                    "absolute_url": f"https://www.courtlistener.com{item.get('absolute_url', '')}",
                    "citation_count": item.get("citeCount") or item.get("citation_count", 0),
                    "cluster_id": item.get("cluster_id")  # Keep original for reference
                })
            
            return {
                "status": "success",
                "count": result.get("count", 0),
                "results": processed_results,
                "query": query,
                "parameters": params
            }
            
        except Exception as e:
            logger.error(f"Opinion search failed: {str(e)}")
            return {"status": "error", "message": f"Search failed: {str(e)}"}
    
    async def import_opinion(
        self,
        postgres_pool: asyncpg.Pool,
        qdrant_client: QdrantClient,
        graphiti_client: Graphiti,
        openai_client,
        opinion_id: int,
        add_as_snippet: bool = True,
        auto_link_events: bool = True,
        group_id: str = "default"
    ) -> Dict[str, Any]:
        """
        Import a CourtListener opinion into your legal research system.
        
        Args:
            opinion_id: CourtListener opinion ID
            add_as_snippet: Create a snippet in your local system
            auto_link_events: Attempt to link with existing chronology events
            group_id: Group identifier for data organization
        """
        try:
            # First try to get opinion cluster (what search results return)
            logger.info(f"Attempting to import opinion ID: {opinion_id}")
            opinion_cluster = await self.client.get_opinion_cluster(opinion_id)
            logger.info(f"Opinion cluster response type: {type(opinion_cluster)}")
            logger.info(f"Opinion cluster response: {opinion_cluster}")
            
            # Add debug information
            result = {
                "opinion_id": opinion_id,
                "debug_info": {
                    "api_endpoint_used": f"opinion-clusters/{opinion_id}",
                    "cluster_response_keys": list(opinion_cluster.keys()) if isinstance(opinion_cluster, dict) else [],
                    "has_error": opinion_cluster.get("status") == "error" if isinstance(opinion_cluster, dict) else False,
                    "raw_response_type": str(type(opinion_cluster)),
                    "api_key_configured": bool(self.api_key)
                }
            }
            
            # If cluster fails, try individual opinion endpoint
            if opinion_cluster.get("status") == "error":
                logger.warning(f"Cluster endpoint failed, trying opinion endpoint for ID {opinion_id}")
                opinion_cluster = await self.client.get_opinion(opinion_id)
                result["debug_info"]["api_endpoint_used"] = f"opinions/{opinion_id}"
                result["debug_info"]["fallback_used"] = True
            
            # Use cluster data for extraction
            opinion = opinion_cluster
            
            # Create snippet if requested
            if add_as_snippet:
                # Import dependency here to avoid circular imports
                from src.services.legal.snippet_service import SnippetService
                from src.core.database.manager import DatabaseManager
                
                # Use the existing database connections passed to this function
                temp_db_manager = type('TempDBManager', (), {
                    'postgres': postgres_pool,
                    'qdrant': qdrant_client,
                    'graphiti': graphiti_client
                })()
                snippet_service = SnippetService(temp_db_manager)
                
                # Extract key information with multiple field name attempts
                case_name = (
                    opinion.get("case_name") or 
                    opinion.get("caseName") or 
                    opinion.get("case_name_full") or 
                    "Unknown Case"
                )
                
                # Handle different citation formats
                citations = opinion.get("citations", [])
                if not citations and opinion.get("citation"):
                    citations = opinion.get("citation") if isinstance(opinion.get("citation"), list) else [opinion.get("citation")]
                
                citation_string = citations[0] if citations else f"Opinion ID: {opinion_id}"
                
                # Get court information
                court_info = opinion.get("court", {})
                court_name = (
                    court_info.get("full_name") if isinstance(court_info, dict) else str(court_info) if court_info else
                    opinion.get("court_name") or
                    "Unknown Court"
                )
                
                # Get filing date with multiple field attempts
                date_filed = (
                    opinion.get("date_filed") or
                    opinion.get("dateFiled") or 
                    opinion.get("date_created") or
                    None
                )
                
                # Get the opinion text from multiple possible sources
                opinion_text = ""
                text_sources = [
                    opinion.get("plain_text"),
                    opinion.get("html"),
                    opinion.get("text"),
                    opinion.get("full_text")
                ]
                
                for source in text_sources:
                    if source and len(source.strip()) > 100:  # Ensure we get substantial content
                        opinion_text = source
                        break
                
                # If no substantial text found, try getting opinions from cluster
                if not opinion_text and opinion.get("sub_opinions"):
                    for sub_opinion in opinion.get("sub_opinions", []):
                        sub_text = sub_opinion.get("plain_text") or sub_opinion.get("html", "")
                        if sub_text and len(sub_text.strip()) > 100:
                            opinion_text = sub_text
                            break
                
                key_excerpt = opinion_text[:500] + "..." if len(opinion_text) > 500 else opinion_text
                
                # Add extracted info to debug
                result["debug_info"].update({
                    "extracted_case_name": case_name,
                    "extracted_court": court_name,
                    "extracted_date": date_filed,
                    "opinion_text_length": len(opinion_text),
                    "citations_found": len(citations),
                    "has_sub_opinions": bool(opinion.get("sub_opinions"))
                })
                
                # Determine tags based on content
                tags = []
                if "landlord" in opinion_text.lower():
                    tags.append("landlord-tenant")
                if "water" in opinion_text.lower() or "leak" in opinion_text.lower():
                    tags.append("water-damage")
                if "negligence" in opinion_text.lower():
                    tags.append("negligence")
                tags.append("courtlistener-import")
                
                # Add to snippet system using modular service
                snippet_result = await snippet_service.create_snippet(
                    citation=f"{case_name}, {citation_string}",
                    key_language=key_excerpt,
                    tags=tags,
                    context=f"CourtListener ID: {opinion_id}",
                    case_type=opinion.get("type", "civil"),
                    group_id=group_id,
                    openai_api_key=openai_client.api_key if openai_client else ""
                )
                result["snippet_id"] = snippet_result.get("snippet_id")
            
            # Auto-link to events if requested
            if auto_link_events and add_as_snippet and result.get("snippet_id"):
                # Import dependency here to avoid circular imports
                import legal_tools
                
                # Search for related events using semantic search
                search_results = await legal_tools.unified_legal_search(
                    postgres_pool=postgres_pool,
                    qdrant_client=qdrant_client,
                    graphiti_client=graphiti_client,
                    openai_client=openai_client,
                    query=f"{case_name} {' '.join(tags)}",
                    search_type="vector",
                    group_id=group_id
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
                # Ensure table exists
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS courtlistener_cache (
                        courtlistener_id INTEGER PRIMARY KEY,
                        opinion_data JSONB,
                        imported_at TIMESTAMP DEFAULT NOW(),
                        local_snippet_id UUID,
                        group_id TEXT DEFAULT 'default'
                    )
                ''')
                
                # Add group_id column if it doesn't exist (for existing tables)
                try:
                    await conn.execute('''
                        ALTER TABLE courtlistener_cache 
                        ADD COLUMN IF NOT EXISTS group_id TEXT DEFAULT 'default'
                    ''')
                except Exception:
                    # Column might already exist, continue
                    pass
                
                await conn.execute(
                    '''
                    INSERT INTO courtlistener_cache 
                    (courtlistener_id, opinion_data, imported_at, local_snippet_id, group_id)
                    VALUES ($1, $2, NOW(), $3, $4)
                    ON CONFLICT (courtlistener_id) DO UPDATE
                    SET opinion_data = EXCLUDED.opinion_data,
                        imported_at = NOW()
                    ''',
                    opinion_id,
                    json.dumps(opinion),
                    result.get("snippet_id"),
                    group_id
                )
            
            result["status"] = "success"
            return result
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def search_dockets(
        self,
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
        if case_name and case_name.strip():
            query_parts.append(f'case_name:"{case_name.strip()}"')
        if docket_number and docket_number.strip():
            query_parts.append(f'docket_number:"{docket_number.strip()}"')
        
        query = " AND ".join(query_parts) if query_parts else "*"
        
        params = {
            "type": "d",
            "per_page": min(limit, 100)
        }
        
        if court:
            params["court"] = court
        if date_filed_after:
            params["date_filed__gte"] = date_filed_after
        if date_filed_before:
            params["date_filed__lte"] = date_filed_before
        
        try:
            result = await self.client.search_dockets(query, **params)
            
            if result.get("status") == "error":
                return result
            
            processed_results = []
            for item in result.get("results", []):
                processed_results.append({
                    "id": item.get("id"),
                    "case_name": item.get("case_name"),
                    "docket_number": item.get("docket_number"),
                    "court": item.get("court"),
                    "date_filed": item.get("date_filed"),
                    "date_terminated": item.get("date_terminated"),
                    "nature_of_suit": item.get("nature_of_suit"),
                    "absolute_url": f"https://www.courtlistener.com{item.get('absolute_url', '')}",
                    "party_info": item.get("party_info", [])
                })
            
            return {
                "status": "success",
                "count": result.get("count", 0),
                "results": processed_results,
                "query": query,
                "parameters": params
            }
        except Exception as e:
            logger.error(f"Docket search failed: {str(e)}")
            return {"status": "error", "message": f"Search failed: {str(e)}"}
    
    async def find_citing_opinions(
        self,
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
        if not citation or not citation.strip():
            return {"status": "error", "message": "Citation parameter is required"}
        
        try:
            result = await self.client.search_opinions(
                citation.strip(),
                per_page=min(limit, 100)
            )
            
            if result.get("status") == "error":
                return result
            
            citing_opinions = []
            for r in result.get("results", []):
                citing_opinions.append({
                    "case_name": r.get("caseName") or r.get("case_name"),
                    "citation": r.get("citation", [""])[0] if r.get("citation") else "",
                    "date": r.get("dateFiled") or r.get("date_filed"),
                    "court": r.get("court"),
                    "snippet": r.get("snippet", "")
                })
            
            return {
                "status": "success",
                "cited_case": citation,
                "citing_count": result.get("count", 0),
                "citing_opinions": citing_opinions
            }
        except Exception as e:
            logger.error(f"Citation search failed: {str(e)}")
            return {"status": "error", "message": f"Search failed: {str(e)}"}
    
    async def analyze_precedents(
        self,
        topic: str,
        jurisdiction: Optional[str] = None,
        min_citations: int = 5,
        date_range_years: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze precedent evolution on a topic using CourtListener data.
        
        This method:
        1. Searches for relevant opinions
        2. Identifies the most-cited cases
        3. Tracks how the law has evolved
        """
        end_date = datetime.now().date()
        start_date = date(end_date.year - date_range_years, end_date.month, end_date.day)
        
        try:
            results = await self.client.search_opinions(
                topic,
                court=jurisdiction,
                filed_after=str(start_date),
                filed_before=str(end_date),
                cited_gt=min_citations,
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
                "trend": self._analyze_legal_trend(periods)
            }
            
            return {
                "status": "success",
                "analysis": analysis
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def _analyze_legal_trend(self, periods: Dict) -> str:
        """Analyze how legal precedent has evolved over time"""
        if not periods:
            return "Insufficient data for trend analysis"
        
        sorted_decades = sorted(periods.keys())
        if len(sorted_decades) < 2:
            return "Limited time range for trend analysis"
        
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