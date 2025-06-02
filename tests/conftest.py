"""
Shared test fixtures and configuration for SueChef tests.
"""

import asyncio
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncGenerator, Generator

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import our application modules
from src.config.settings import get_config, reset_config
from src.core.database.manager import DatabaseManager


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_config():
    """Provide mocked configuration for testing."""
    config = get_config()
    # Override with test values
    config.database.postgres_url = "postgresql://test:test@localhost:5433/test_db"
    config.database.qdrant_url = "http://localhost:6334"
    config.database.neo4j_url = "bolt://localhost:7688"
    config.openai.api_key = "test-openai-key"
    return config


@pytest.fixture
def mock_db_manager():
    """Provide mocked database manager for unit tests."""
    db_manager = MagicMock()
    
    # Mock PostgreSQL pool
    postgres_mock = AsyncMock()
    postgres_conn_mock = AsyncMock()
    postgres_mock.acquire.return_value.__aenter__.return_value = postgres_conn_mock
    postgres_mock.acquire.return_value.__aexit__.return_value = None
    db_manager.postgres = postgres_mock
    
    # Mock Qdrant client
    qdrant_mock = MagicMock()
    db_manager.qdrant = qdrant_mock
    
    # Mock Graphiti client
    graphiti_mock = AsyncMock()
    db_manager.graphiti = graphiti_mock
    
    return db_manager


@pytest.fixture
def mock_openai_client():
    """Provide mocked OpenAI client for testing."""
    client_mock = AsyncMock()
    
    # Mock embedding response
    embedding_response = MagicMock()
    embedding_response.data = [MagicMock()]
    embedding_response.data[0].embedding = [0.1] * 1536  # Standard embedding size
    client_mock.embeddings.create.return_value = embedding_response
    
    return client_mock


@pytest.fixture
async def test_db_manager(mock_config) -> AsyncGenerator[DatabaseManager, None]:
    """
    Provide real database manager for integration tests.
    
    Note: This requires test databases to be running.
    Use docker-compose-test.yml for isolated test environment.
    """
    db_manager = DatabaseManager(mock_config.database)
    
    try:
        await db_manager.initialize()
        yield db_manager
    finally:
        await db_manager.cleanup()


@pytest.fixture
def mock_courtlistener_response():
    """Provide typical CourtListener API response for testing."""
    return {
        "count": 1,
        "results": [
            {
                "id": 12345,
                "case_name": "Test v. Example",
                "court": "Test District Court",
                "date_filed": "2024-01-01",
                "plain_text": "This is a test legal opinion with substantive content...",
                "citations": ["123 F.3d 456"],
                "status": "Published"
            }
        ]
    }


@pytest.fixture
def sample_event_data():
    """Provide sample event data for testing."""
    return {
        "date": "2024-01-01",
        "description": "Contract signing ceremony",
        "parties": ["Alice Corp", "Bob LLC"],
        "tags": ["contract", "commercial"],
        "significance": "Major commercial agreement",
        "group_id": "test_group"
    }


@pytest.fixture
def sample_snippet_data():
    """Provide sample snippet data for testing."""
    return {
        "citation": "Test v. Example, 123 F.3d 456 (2024)",
        "key_language": "The court held that contracts must have consideration.",
        "context": "This case established important precedent for contract law.",
        "case_type": "civil",
        "tags": ["contract", "consideration"],
        "group_id": "test_group"
    }


@pytest.fixture(autouse=True)
def reset_configuration():
    """Reset configuration before each test to ensure isolation."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing."""
    with patch.dict('os.environ', {
        'OPENAI_API_KEY': 'test-openai-key',
        'COURTLISTENER_API_KEY': 'test-courtlistener-key',
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5433',
        'POSTGRES_DB': 'test_db',
        'POSTGRES_USER': 'test',
        'POSTGRES_PASSWORD': 'test',
        'QDRANT_URL': 'http://localhost:6334',
        'NEO4J_URL': 'bolt://localhost:7688',
        'NEO4J_USER': 'test',
        'NEO4J_PASSWORD': 'test'
    }):
        yield


class MockAsyncContextManager:
    """Helper class for mocking async context managers."""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
        
    async def __aenter__(self):
        return self.return_value
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass