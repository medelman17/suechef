"""Snippet management service for SueChef."""

import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from qdrant_client.models import PointStruct
from graphiti_core.nodes import EpisodeType
import openai

from ..base import BaseService
from ...utils.embeddings import get_embedding


class SnippetService(BaseService):
    """Service for managing legal research snippets."""
    
    async def create_snippet(
        self,
        citation: str,
        key_language: str,
        tags: Optional[List[str]] = None,
        context: Optional[str] = None,
        case_type: Optional[str] = None,
        group_id: str = "default",
        openai_api_key: str = ""
    ) -> Dict[str, Any]:
        """Create a legal research snippet with automatic entity extraction."""
        
        try:
            # Insert into PostgreSQL
            async with self.db.postgres.acquire() as conn:
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
            openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
            full_text = f"{citation} {key_language} {context or ''}"
            embedding = await get_embedding(full_text, openai_client)
            
            self.db.qdrant.upsert(
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
            
            # Add to Graphiti knowledge graph
            content = f"Legal Precedent: {citation}\\n{key_language}"
            if context:
                content += f"\\nContext: {context}"
            
            await self.db.graphiti.add_episode(
                name=f"Legal Snippet - {citation}",
                episode_body=content,
                source=EpisodeType.text,
                source_description=citation,
                reference_time=datetime.now(),
                group_id=group_id
            )
            
            return self._success_response(
                data={"snippet_id": str(snippet_id)},
                message="Snippet added to all systems successfully"
            )
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to create snippet: {str(e)}",
                error_type="creation_error"
            )
    
    async def get_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """Get a single snippet by ID."""
        
        try:
            async with self.db.postgres.acquire() as conn:
                snippet = await conn.fetchrow(
                    """
                    SELECT id, citation, key_language, tags, context, 
                           case_type, created_at, updated_at, group_id
                    FROM snippets
                    WHERE id = $1
                    """,
                    uuid.UUID(snippet_id)
                )
            
            if not snippet:
                return self._error_response("Snippet not found", "not_found")
            
            # Convert to dict and parse JSON fields
            snippet_dict = dict(snippet)
            snippet_dict["tags"] = json.loads(snippet_dict["tags"])
            snippet_dict["id"] = str(snippet_dict["id"])
            
            return self._success_response(data=snippet_dict)
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to get snippet: {str(e)}",
                error_type="retrieval_error"
            )
    
    async def list_snippets(
        self,
        limit: int = 50,
        offset: int = 0,
        case_type: Optional[str] = None,
        tags_filter: Optional[List[str]] = None,
        group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List snippets with optional filtering."""
        
        try:
            # Build query conditions
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
            
            if group_id:
                param_count += 1
                conditions.append(f"group_id = ${param_count}")
                params.append(group_id)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            async with self.db.postgres.acquire() as conn:
                # Get total count
                count_query = f"SELECT COUNT(*) FROM snippets {where_clause}"
                total_count = await conn.fetchval(count_query, *params)
                
                # Add limit and offset to params
                param_count += 1
                params.append(limit)
                param_count += 1
                params.append(offset)
                
                # Get snippets
                snippets_query = f"""
                    SELECT id, citation, key_language, tags, case_type, group_id
                    FROM snippets
                    {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${param_count-1} OFFSET ${param_count}
                """
                
                snippets = await conn.fetch(snippets_query, *params)
            
            # Convert to list of dicts
            snippets_list = []
            for snippet in snippets:
                snippet_dict = dict(snippet)
                snippet_dict["tags"] = json.loads(snippet_dict["tags"])
                snippet_dict["id"] = str(snippet_dict["id"])
                snippets_list.append(snippet_dict)
            
            return self._success_response(
                data={
                    "snippets": snippets_list,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset
                }
            )
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to list snippets: {str(e)}",
                error_type="retrieval_error"
            )
    
    async def update_snippet(
        self,
        snippet_id: str,
        citation: Optional[str] = None,
        key_language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        context: Optional[str] = None,
        case_type: Optional[str] = None,
        openai_api_key: str = ""
    ) -> Dict[str, Any]:
        """Update an existing snippet."""
        
        try:
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
                return self._error_response("No fields to update", "validation_error")
            
            # Add updated_at timestamp
            param_count += 1
            updates.append(f"updated_at = ${param_count}")
            params.append(datetime.now())
            
            # Add snippet_id for WHERE clause
            param_count += 1
            params.append(uuid.UUID(snippet_id))
            
            async with self.db.postgres.acquire() as conn:
                # Update PostgreSQL
                update_query = f"""
                    UPDATE snippets
                    SET {', '.join(updates)}
                    WHERE id = ${param_count}
                    RETURNING id, citation, key_language, tags, context, case_type, group_id
                """
                
                updated_snippet = await conn.fetchrow(update_query, *params)
                
                if not updated_snippet:
                    return self._error_response("Snippet not found", "not_found")
            
            # Update Qdrant if citation, key_language, or context changed
            if citation is not None or key_language is not None or context is not None:
                # Get full snippet data for embedding
                snippet_data = dict(updated_snippet)
                full_text = f"{snippet_data['citation']} {snippet_data['key_language']} {snippet_data.get('context', '')}"
                
                openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
                embedding = await get_embedding(full_text, openai_client)
                
                self.db.qdrant.upsert(
                    collection_name="legal_snippets",
                    points=[
                        PointStruct(
                            id=str(snippet_id),
                            vector=embedding,
                            payload={
                                "citation": snippet_data['citation'],
                                "key_language": snippet_data['key_language'][:200],
                                "tags": json.loads(snippet_data['tags']),
                                "case_type": snippet_data['case_type'],
                                "type": "snippet",
                                "group_id": snippet_data['group_id']
                            }
                        )
                    ]
                )
            
            # Convert response
            snippet_dict = dict(updated_snippet)
            snippet_dict["tags"] = json.loads(snippet_dict["tags"])
            snippet_dict["id"] = str(snippet_dict["id"])
            
            return self._success_response(
                data=snippet_dict,
                message="Snippet updated successfully"
            )
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to update snippet: {str(e)}",
                error_type="update_error"
            )
    
    async def delete_snippet(self, snippet_id: str) -> Dict[str, Any]:
        """Delete a snippet from all systems."""
        
        try:
            async with self.db.postgres.acquire() as conn:
                # Delete from PostgreSQL (cascade will handle manual_links)
                deleted = await conn.fetchval(
                    "DELETE FROM snippets WHERE id = $1 RETURNING id",
                    uuid.UUID(snippet_id)
                )
                
                if not deleted:
                    return self._error_response("Snippet not found", "not_found")
            
            # Delete from Qdrant
            try:
                self.db.qdrant.delete(
                    collection_name="legal_snippets",
                    points_selector=[str(snippet_id)]
                )
            except Exception as e:
                # Log but don't fail if Qdrant delete fails
                pass
            
            return self._success_response(
                data={"snippet_id": str(snippet_id)},
                message="Snippet deleted successfully"
            )
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to delete snippet: {str(e)}",
                error_type="deletion_error"
            )