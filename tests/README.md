# SueChef Testing Guide

This directory contains the pytest-based test suite for SueChef, implementing multiple testing layers following FastMCP best practices.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── unit/                    # Fast, isolated unit tests
│   ├── services/           # Service layer tests with mocked dependencies
│   ├── utils/              # Utility function tests
│   └── external/           # External service client tests (mocked)
├── integration/            # Integration tests
│   ├── tools/              # FastMCP tool tests (in-memory)
│   └── database/           # Database integration tests
└── e2e/                    # End-to-end tests (full system)
```

## Running Tests

### Quick Start
```bash
# Run all unit tests (fast)
uv run pytest tests/unit/ -v

# Run specific test file
uv run pytest tests/unit/utils/test_parameter_parsing.py -v

# Run with coverage
uv run pytest tests/unit/ --cov=src --cov-report=html
```

### Test Categories
```bash
# Unit tests only (fast, no external dependencies)
uv run pytest -m unit

# Integration tests (requires databases)
uv run pytest -m integration

# All tests except slow ones
uv run pytest -m "not slow"
```

## Testing Patterns

### 1. Unit Tests (Fast, Isolated)
Unit tests focus on individual components with all dependencies mocked:

```python
def test_service_method(mock_db_manager):
    service = EventService(mock_db_manager)
    result = service.some_method()
    assert result["status"] == "success"
```

### 2. FastMCP Tool Tests (In-Memory)
Following https://gofastmcp.com/patterns/testing patterns:

```python
async def test_mcp_tool(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("tool_name", {"param": "value"})
        assert result[0].text  # Verify response
```

### 3. Integration Tests (Real Components)
Test actual database interactions and service integrations:

```python
async def test_database_operation(test_db_manager):
    # Test with real database connections
    result = await service.create_event(test_data)
    assert result["status"] == "success"
```

## Current Test Status

✅ **Working Tests:**
- Parameter parsing utilities (7 tests)
- Service creation and inheritance (3 tests)  
- Test infrastructure and fixtures

🔄 **In Progress:**
- FastMCP tool integration tests
- Async service method mocking
- Database integration tests

## Configuration

Tests use `pytest.ini` for configuration with these key settings:
- Async tests with `pytest-asyncio`
- Test markers for categorization
- Automatic test discovery
- Warning filters

## Fixtures

Key fixtures available in `conftest.py`:
- `mock_db_manager` - Mocked database manager for unit tests
- `mock_config` - Test configuration
- `test_db_manager` - Real database manager for integration tests
- `sample_event_data` - Sample test data

## Best Practices

1. **Fast Unit Tests**: Mock all external dependencies
2. **Isolated Tests**: Each test should be independent
3. **Clear Naming**: Test names should describe what they verify
4. **Focused Tests**: One assertion per test when possible
5. **Proper Markers**: Use `@pytest.mark.asyncio` for async tests

## Adding New Tests

1. Choose the appropriate test layer (unit/integration/e2e)
2. Use existing fixtures from `conftest.py`
3. Follow naming conventions (`test_*.py`)
4. Add appropriate pytest markers
5. Mock external dependencies for unit tests