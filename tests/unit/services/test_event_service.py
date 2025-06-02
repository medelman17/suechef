"""
Unit tests for EventService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.legal.event_service import EventService


class TestEventService:
    """Test EventService business logic with mocked dependencies."""

    def test_event_service_creation(self, mock_db_manager):
        """Test that EventService can be created with a database manager."""
        service = EventService(mock_db_manager)
        assert service.db == mock_db_manager

    @pytest.mark.asyncio
    async def test_add_event_success(self, mock_db_manager, sample_event_data):
        """Test successful event creation."""
        # Setup mocks
        mock_conn = mock_db_manager.postgres.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = {
            'id': 'test-uuid-123',
            'date': '2024-01-01',
            'description': 'Contract signing ceremony',
            'parties': '["Alice Corp", "Bob LLC"]',
            'tags': '["contract", "commercial"]',
            'significance': 'Major commercial agreement',
            'group_id': 'test_group'
        }
        
        # Create service and call method
        service = EventService(mock_db_manager)
        result = await service.add_event(**sample_event_data)
        
        # Verify result
        assert result["status"] == "success"
        assert result["data"]["id"] == "test-uuid-123"
        assert result["data"]["description"] == "Contract signing ceremony"
        
        # Verify database was called
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_event_validation_error(self, mock_db_manager):
        """Test event creation with invalid data."""
        service = EventService(mock_db_manager)
        
        # Missing required field
        result = await service.add_event(
            date="invalid-date",  # Invalid date format
            description=""  # Empty description
        )
        
        assert result["status"] == "error"
        assert "validation" in result["message"].lower() or "invalid" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_get_event_success(self, mock_db_manager):
        """Test successful event retrieval."""
        # Setup mock
        mock_conn = mock_db_manager.postgres.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = {
            'id': 'test-uuid-123',
            'date': '2024-01-01',
            'description': 'Test event',
            'parties': '[]',
            'tags': '[]',
            'significance': None,
            'group_id': 'default'
        }
        
        service = EventService(mock_db_manager)
        result = await service.get_event("test-uuid-123")
        
        assert result["status"] == "success"
        assert result["data"]["id"] == "test-uuid-123"

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, mock_db_manager):
        """Test event retrieval when event doesn't exist."""
        # Setup mock to return None
        mock_conn = mock_db_manager.postgres.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow.return_value = None
        
        service = EventService(mock_db_manager)
        result = await service.get_event("nonexistent-id")
        
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()