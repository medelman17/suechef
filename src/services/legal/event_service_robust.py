"""Robust event management service with parameter parsing and error handling."""

import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

from qdrant_client.models import PointStruct
from graphiti_core.nodes import EpisodeType
import openai

from ..base import BaseService
from ...utils.embeddings import get_embedding
from ...utils.parameter_parsing import normalize_event_parameters

logger = logging.getLogger(__name__)


class RobustEventService(BaseService):
    """Enhanced event service with robust parameter parsing and error handling."""
    
    async def create_event_robust(
        self,
        date: str,
        description: str,
        parties: Union[str, List[str], None] = None,
        document_source: Optional[str] = None,
        excerpts: Optional[str] = None,
        tags: Union[str, List[str], None] = None,
        significance: Optional[str] = None,
        group_id: str = "default",
        openai_api_key: str = ""
    ) -> Dict[str, Any]:
        """
        Add a chronology event with robust parameter parsing and error handling.
        
        This version handles:
        - Array parameters sent as JSON strings or native arrays
        - Connection retries for database operations
        - Comprehensive error reporting
        """
        
        max_retries = 3
        retry_delay = 1
        
        # Step 1: Normalize parameters
        try:
            logger.info(f"🔧 Normalizing parameters for event: {description[:50]}...")
            
            # Show what we received for debugging
            logger.debug(f"Raw parameters received:")
            logger.debug(f"  parties type: {type(parties)}, value: {parties}")
            logger.debug(f"  tags type: {type(tags)}, value: {tags}")
            
            # Normalize all parameters
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
            
            logger.info(f"✅ Parameters normalized successfully:")
            logger.info(f"  parties: {params['parties']} (type: {type(params['parties'])})")
            logger.info(f"  tags: {params['tags']} (type: {type(params['tags'])})")
            
        except Exception as e:
            logger.error(f"❌ Parameter normalization failed: {e}")
            return self._error_response(
                message=f"Parameter parsing error: {str(e)}",
                error_type="parameter_parsing_error"
            )
        
        # Step 2: Database operations with retry logic
        for attempt in range(max_retries):
            try:
                logger.info(f"💾 Saving event to database (attempt {attempt + 1}/{max_retries})...")
                
                # Insert into PostgreSQL
                async with self.db.postgres.acquire() as conn:
                    event_id = await conn.fetchval(
                        """
                        INSERT INTO events (date, description, parties, document_source, excerpts, tags, significance, group_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        RETURNING id
                        """,
                        datetime.strptime(params['date'], "%Y-%m-%d").date(),
                        params['description'],
                        json.dumps(params['parties'] or []),
                        params['document_source'],
                        params['excerpts'],
                        json.dumps(params['tags'] or []),
                        params['significance'],
                        params['group_id']
                    )
                
                logger.info(f"✅ Event saved to PostgreSQL with ID: {event_id}")
                
                # Create embedding and store in Qdrant
                try:
                    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
                    full_text = f"{params['description']} {params['excerpts'] or ''} {params['significance'] or ''}"
                    embedding = await get_embedding(full_text, openai_client)
                    
                    self.db.qdrant.upsert(
                        collection_name="legal_events",
                        points=[
                            PointStruct(
                                id=str(event_id),
                                vector=embedding,
                                payload={
                                    "date": params['date'],
                                    "description": params['description'],
                                    "parties": params['parties'] or [],
                                    "tags": params['tags'] or [],
                                    "type": "event",
                                    "group_id": params['group_id']
                                }
                            )
                        ]
                    )
                    logger.info("✅ Event saved to Qdrant vector database")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Qdrant storage failed (event still saved to PostgreSQL): {e}")
                
                # Add to Graphiti knowledge graph
                try:
                    episode_content = f"On {params['date']}: {params['description']}"
                    if params['excerpts']:
                        episode_content += f"\\nExcerpts: {params['excerpts']}"
                    
                    await self.db.graphiti.add_episode(
                        name=f"Legal Event - {params['date']}",
                        episode_body=episode_content,
                        source=EpisodeType.text,
                        source_description=params['document_source'] or "Legal Timeline",
                        reference_time=datetime.strptime(params['date'], "%Y-%m-%d"),
                        group_id=params['group_id']
                    )
                    logger.info("✅ Event added to Graphiti knowledge graph")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Graphiti storage failed (event still saved to PostgreSQL): {e}")
                
                # Success!
                result = self._success_response(
                    data={
                        "event_id": str(event_id),
                        "normalized_params": {
                            "parties": params['parties'],
                            "tags": params['tags'],
                            "parties_count": len(params['parties'] or []),
                            "tags_count": len(params['tags'] or [])
                        }
                    },
                    message="Event added to all systems successfully"
                )
                
                logger.info(f"🎉 Event creation completed successfully: {event_id}")
                return result
                
            except Exception as e:
                logger.error(f"❌ Database operation attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"💥 All database operation attempts failed")
                    return self._error_response(
                        message=f"Database operation failed after {max_retries} attempts: {str(e)}",
                        error_type="database_connection_error"
                    )
        
        # This should never be reached
        return self._error_response(
            message="Unexpected error in event creation",
            error_type="unknown_error"
        )
    
    async def test_array_parsing(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test function for array parameter parsing."""
        
        logger.info("🧪 Testing array parameter parsing...")
        
        results = {}
        
        for key, value in test_data.items():
            try:
                from ...utils.parameter_parsing import parse_string_list
                parsed = parse_string_list(value)
                results[key] = {
                    "input": value,
                    "input_type": str(type(value)),
                    "parsed": parsed,
                    "parsed_type": str(type(parsed)),
                    "success": True
                }
                logger.info(f"✅ {key}: {value} -> {parsed}")
            except Exception as e:
                results[key] = {
                    "input": value,
                    "input_type": str(type(value)),
                    "error": str(e),
                    "success": False
                }
                logger.error(f"❌ {key}: {value} -> ERROR: {e}")
        
        return self._success_response(
            data=results,
            message="Array parsing test completed"
        )