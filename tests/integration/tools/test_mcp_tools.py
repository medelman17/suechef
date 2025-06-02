"""
Integration tests for MCP tools using FastMCP in-memory testing.
"""

import pytest
import json
from mcp import Client
from unittest.mock import patch, AsyncMock


# We need to import and configure the server for testing
# This would need to be adjusted based on how main.py is structured
@pytest.fixture
def mcp_server():
    """Create FastMCP server instance for testing."""
    # Import here to avoid circular imports and initialization issues
    import sys
    import os
    
    # Add project root to path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))
    
    # Mock environment variables to avoid real service connections
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-key',
        'COURTLISTENER_API_KEY': 'test-key',
        'POSTGRES_HOST': 'test',
        'POSTGRES_PORT': '5432',
        'POSTGRES_DB': 'test',
        'POSTGRES_USER': 'test',
        'POSTGRES_PASSWORD': 'test'
    }):
        try:
            from main import mcp
            return mcp
        except Exception:
            # If main.py can't be imported due to dependencies, skip these tests
            pytest.skip("Cannot import main.py - database dependencies not available")


class TestMCPTools:
    """Test MCP tools using FastMCP in-memory pattern."""

    @pytest.mark.integration
    async def test_test_array_parameters_tool(self, mcp_server):
        """Test the test_array_parameters tool."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("test_array_parameters", {
                "test_parties": ["Party A", "Party B"],
                "test_tags": ["tag1", "tag2"]
            })
            
            # Verify response structure
            assert len(result) > 0
            response_text = result[0].text
            
            # Parse JSON response
            response_data = json.loads(response_text)
            assert response_data["status"] == "success"
            assert "results" in response_data

    @pytest.mark.integration  
    @patch('src.services.legal.event_service.EventService.add_event')
    async def test_add_event_tool_mocked(self, mock_add_event, mcp_server):
        """Test add_event tool with mocked service."""
        # Mock the service response
        mock_add_event.return_value = {
            "status": "success",
            "data": {
                "id": "test-123",
                "description": "Test event",
                "date": "2024-01-01"
            }
        }
        
        async with Client(mcp_server) as client:
            result = await client.call_tool("add_event", {
                "date": "2024-01-01",
                "description": "Test contract signing",
                "group_id": "test"
            })
            
            # Verify tool was called and returned expected response
            assert len(result) > 0
            response_text = result[0].text
            
            # Parse response
            response_data = json.loads(response_text)
            assert response_data["status"] == "success"
            assert response_data["data"]["id"] == "test-123"
            
            # Verify service was called with correct parameters
            mock_add_event.assert_called_once()
            call_args = mock_add_event.call_args[1]  # keyword arguments
            assert call_args["date"] == "2024-01-01"
            assert call_args["description"] == "Test contract signing"

    @pytest.mark.integration
    @patch('src.services.external.courtlistener_service.CourtListenerService.test_connection')
    async def test_courtlistener_connection_tool(self, mock_test_connection, mcp_server):
        """Test CourtListener connection tool with mocked service."""
        # Mock successful connection
        mock_test_connection.return_value = {
            "status": "success",
            "message": "Connection successful",
            "test_search_count": 100
        }
        
        async with Client(mcp_server) as client:
            result = await client.call_tool("test_courtlistener_connection", {})
            
            assert len(result) > 0
            response_text = result[0].text
            
            response_data = json.loads(response_text)
            assert response_data["status"] == "success"
            assert "Connection successful" in response_data["message"]