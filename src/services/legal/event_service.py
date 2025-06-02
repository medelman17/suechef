"""Event management service for SueChef."""

import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from qdrant_client.models import PointStruct
from graphiti_core.nodes import EpisodeType
import openai

from ..base import BaseService
from ...utils.embeddings import get_embedding


class EventService(BaseService):
    """Service for managing legal events and chronology."""
    
    async def create_event(
        self,
        date: str,
        description: str,
        parties: Optional[List[str]] = None,
        document_source: Optional[str] = None,
        excerpts: Optional[str] = None,
        tags: Optional[List[str]] = None,
        significance: Optional[str] = None,
        group_id: str = "default",
        openai_api_key: str = ""
    ) -> Dict[str, Any]:
        """Add a chronology event with automatic vector and knowledge graph storage."""
        
        try:
            # Insert into PostgreSQL
            async with self.db.postgres.acquire() as conn:
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
            openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
            full_text = f"{description} {excerpts or ''} {significance or ''}"
            embedding = await get_embedding(full_text, openai_client)
            
            self.db.qdrant.upsert(
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
            
            await self.db.graphiti.add_episode(
                name=f"Legal Event - {date}",
                episode_body=episode_content,
                source=EpisodeType.text,
                source_description=document_source or "Legal Timeline",
                reference_time=datetime.strptime(date, "%Y-%m-%d"),
                group_id=group_id
            )
            
            return self._success_response(
                data={"event_id": str(event_id)},
                message="Event added to all systems successfully"
            )
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to create event: {str(e)}",
                error_type="creation_error"
            )
    
    async def get_event(self, event_id: str) -> Dict[str, Any]:
        """Get a single event by ID."""
        
        try:
            async with self.db.postgres.acquire() as conn:
                event = await conn.fetchrow(
                    "SELECT * FROM events WHERE id = $1",
                    uuid.UUID(event_id)
                )
            
            if not event:
                return self._error_response("Event not found", "not_found")
            
            # Convert to dict and parse JSON fields
            event_dict = dict(event)
            event_dict["parties"] = json.loads(event_dict["parties"])
            event_dict["tags"] = json.loads(event_dict["tags"])
            event_dict["id"] = str(event_dict["id"])
            
            return self._success_response(data=event_dict)
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to get event: {str(e)}",
                error_type="retrieval_error"
            )
    
    async def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        parties_filter: Optional[List[str]] = None,
        tags_filter: Optional[List[str]] = None,
        group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """List events with optional filtering."""
        
        try:
            # Build query conditions
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
            
            if group_id:
                param_count += 1
                conditions.append(f"group_id = ${param_count}")
                params.append(group_id)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # Add limit and offset
            param_count += 1
            params.append(limit)
            limit_clause = f"LIMIT ${param_count}"
            
            param_count += 1
            params.append(offset)
            offset_clause = f"OFFSET ${param_count}"
            
            query = f"""
                SELECT * FROM events 
                {where_clause}
                ORDER BY date DESC, created_at DESC
                {limit_clause} {offset_clause}
            """
            
            async with self.db.postgres.acquire() as conn:
                # Get total count first
                count_query = f"SELECT COUNT(*) FROM events {where_clause}"
                total_count = await conn.fetchval(count_query, *(params[:-2]))  # Exclude limit/offset params
                
                # Get events
                events = await conn.fetch(query, *params)
            
            # Convert to list of dicts
            events_list = []
            for event in events:
                event_dict = dict(event)
                event_dict["parties"] = json.loads(event_dict["parties"])
                event_dict["tags"] = json.loads(event_dict["tags"])
                event_dict["id"] = str(event_dict["id"])
                events_list.append(event_dict)
            
            return self._success_response(
                data={
                    "events": events_list,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset
                }
            )
            
        except Exception as e:
            return self._error_response(
                message=f"Failed to list events: {str(e)}",
                error_type="retrieval_error"
            )

    async def update_event(
        self,
        event_id: str,
        date: Optional[str] = None,
        description: Optional[str] = None,
        parties: Optional[List[str]] = None,
        document_source: Optional[str] = None,
        excerpts: Optional[str] = None,
        tags: Optional[List[str]] = None,
        significance: Optional[str] = None,
        openai_api_key: str = ""
    ) -> Dict[str, Any]:
        """Update an existing event."""
        
        try:
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
                return self._error_response("No fields provided for update", "validation_error")
            
            # Add updated_at timestamp
            param_count += 1
            updates.append(f"updated_at = ${param_count}")
            params.append(datetime.utcnow())
            
            # Add event_id for WHERE clause
            param_count += 1
            params.append(uuid.UUID(event_id))
            
            # Execute update
            async with self.db.postgres.acquire() as conn:
                updated_event = await conn.fetchrow(
                    f"""
                    UPDATE events SET {', '.join(updates)}
                    WHERE id = ${param_count}
                    RETURNING id, date, description, parties, document_source, excerpts, tags, significance, group_id, created_at, updated_at
                    """,
                    *params
                )
                
                if not updated_event:
                    return self._error_response("Event not found", "not_found")
            
            # Update vector embedding if description changed
            if description is not None:
                try:
                    openai_client = openai.AsyncOpenAI(api_key=openai_api_key)
                    full_text = f"{description} {excerpts or ''}"
                    embedding = await get_embedding(full_text, openai_client)
                    
                    # Update in Qdrant
                    self.db.qdrant.upsert(
                        collection_name="legal_events",
                        points=[PointStruct(
                            id=str(event_id),
                            vector=embedding,
                            payload={
                                "type": "event",
                                "description": description,
                                "date": date or str(updated_event["date"]),
                                "parties": parties or json.loads(updated_event["parties"] or "[]"),
                                "tags": tags or json.loads(updated_event["tags"] or "[]"),
                                "group_id": updated_event["group_id"]
                            }
                        )]
                    )
                except Exception as e:
                    # Vector update failed, but PostgreSQL update succeeded
                    pass
            
            # Update knowledge graph if needed
            if description is not None:
                try:
                    await self.db.graphiti.add_episode(
                        name=f"Event Update: {description[:50]}...",
                        episode_body=f"Updated legal event: {description}. {excerpts or ''}",
                        source_description=f"Legal event update {event_id}",
                        source=EpisodeType.text,
                        group_id=updated_event["group_id"]
                    )
                except Exception as e:
                    # Knowledge graph update failed, but core update succeeded
                    pass
            
            # Format response
            event_dict = dict(updated_event)
            event_dict["parties"] = json.loads(event_dict["parties"] or "[]")
            event_dict["tags"] = json.loads(event_dict["tags"] or "[]")
            event_dict["id"] = str(event_dict["id"])
            
            return self._success_response(
                data=event_dict,
                message="Event updated successfully"
            )
            
        except ValueError as e:
            if "UUID" in str(e):
                return self._error_response("Invalid event ID format", "validation_error")
            elif "time data" in str(e):
                return self._error_response("Invalid date format. Use YYYY-MM-DD", "validation_error")
            else:
                return self._error_response(f"Validation error: {str(e)}", "validation_error")
        except Exception as e:
            return self._error_response(
                message=f"Failed to update event: {str(e)}",
                error_type="update_error"
            )

    async def delete_event(self, event_id: str) -> Dict[str, Any]:
        """Delete an event from all systems."""
        
        try:
            async with self.db.postgres.acquire() as conn:
                # Get event details before deletion for cleanup
                event = await conn.fetchrow(
                    "SELECT group_id, description FROM events WHERE id = $1",
                    uuid.UUID(event_id)
                )
                
                if not event:
                    return self._error_response("Event not found", "not_found")
                
                # Delete from PostgreSQL (cascade will handle related records)
                deleted = await conn.fetchval(
                    "DELETE FROM events WHERE id = $1 RETURNING id",
                    uuid.UUID(event_id)
                )
            
            # Delete from Qdrant
            try:
                self.db.qdrant.delete(
                    collection_name="legal_events",
                    points_selector=[str(event_id)]
                )
            except Exception as e:
                # Qdrant deletion failed, but PostgreSQL deletion succeeded
                pass
            
            # Note: We don't delete from Graphiti as episodes represent historical knowledge
            # that should be preserved even if the source event is deleted
            
            return self._success_response(
                data={"deleted_id": str(deleted)},
                message="Event deleted successfully"
            )
            
        except ValueError as e:
            if "UUID" in str(e):
                return self._error_response("Invalid event ID format", "validation_error")
            else:
                return self._error_response(f"Validation error: {str(e)}", "validation_error")
        except Exception as e:
            return self._error_response(
                message=f"Failed to delete event: {str(e)}",
                error_type="deletion_error"
            )