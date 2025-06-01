# SueChef Modularization Proposal

## Current Issues

### 📊 File Size Analysis
- `main.py`: **656 lines** - Server setup, 26 tools, 6 resources, 6 prompts
- `legal_tools.py`: **1158 lines** - All tool implementations in one file
- `courtlistener_tools.py`: **458 lines** - Integration tools
- Total: **2908 lines** across 7 files

### 🚫 Problems with Current Structure
1. **Monolithic Files**: Hard to navigate, test, and maintain
2. **Mixed Concerns**: Server logic mixed with business logic
3. **Tight Coupling**: Database initialization tied to server startup
4. **Testing Challenges**: No clear boundaries for unit testing
5. **Scalability Issues**: Adding new tools requires modifying large files
6. **Code Discovery**: Hard to find specific functionality

## 🎯 Proposed Modular Structure

### 1. Core Infrastructure Layer
```
src/
├── core/
│   ├── __init__.py
│   ├── config.py              # Centralized configuration management
│   ├── exceptions.py          # Custom exceptions and error handling
│   ├── database/
│   │   ├── __init__.py
│   │   ├── manager.py         # Database connection manager
│   │   ├── postgres.py        # PostgreSQL client & operations
│   │   ├── qdrant.py          # Qdrant client & operations
│   │   ├── graphiti.py        # Graphiti client & operations
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── postgres.sql   # PostgreSQL schema
│   │       └── qdrant.py      # Qdrant collection configs
│   └── clients/
│       ├── __init__.py
│       ├── factory.py         # Client factory pattern
│       └── lifecycle.py       # Client lifecycle management
```

### 2. Domain Models Layer
```
src/
├── models/
│   ├── __init__.py
│   ├── base.py                # Base model classes
│   ├── legal/
│   │   ├── __init__.py
│   │   ├── entities.py        # Legal domain entities (Judge, Attorney, etc.)
│   │   ├── events.py          # Event models
│   │   ├── snippets.py        # Snippet models
│   │   └── cases.py           # Case-related models
│   ├── requests.py            # Request/input models
│   └── responses.py           # Response/output models
```

### 3. Services Layer (Business Logic)
```
src/
├── services/
│   ├── __init__.py
│   ├── base.py                # Base service class
│   ├── legal/
│   │   ├── __init__.py
│   │   ├── event_service.py   # Event CRUD and business logic
│   │   ├── snippet_service.py # Snippet CRUD and business logic
│   │   ├── search_service.py  # Unified search operations
│   │   ├── analytics_service.py # Legal analytics
│   │   └── community_service.py # Community detection
│   ├── external/
│   │   ├── __init__.py
│   │   ├── courtlistener_service.py # CourtListener integration
│   │   └── openai_service.py        # OpenAI embedding service
│   └── system/
│       ├── __init__.py
│       ├── health_service.py  # System health checks
│       └── setup_service.py   # Database initialization
```

### 4. Tools Layer (MCP Interface)
```
src/
├── tools/
│   ├── __init__.py
│   ├── base.py                # Base tool class with common patterns
│   ├── decorators.py          # Tool decorators and utilities
│   ├── registry.py            # Tool registration system
│   ├── legal/
│   │   ├── __init__.py
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── crud_tools.py  # Event CRUD tools
│   │   │   └── search_tools.py # Event search tools
│   │   ├── snippets/
│   │   │   ├── __init__.py
│   │   │   ├── crud_tools.py  # Snippet CRUD tools
│   │   │   └── search_tools.py # Snippet search tools
│   │   ├── analytics/
│   │   │   ├── __init__.py
│   │   │   └── analytics_tools.py # Analytics tools
│   │   └── communities/
│   │       ├── __init__.py
│   │       └── community_tools.py # Community tools
│   ├── external/
│   │   ├── __init__.py
│   │   └── courtlistener_tools.py # CourtListener tools
│   └── system/
│       ├── __init__.py
│       └── system_tools.py    # System health and status tools
```

### 5. MCP Server Layer
```
src/
├── mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP server setup (much smaller)
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── system_resources.py # System-related resources
│   │   └── legal_resources.py  # Legal-related resources
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── legal_prompts.py    # Legal research prompts
│   │   └── workflow_prompts.py # Workflow prompts
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py             # Authentication middleware
│       ├── validation.py       # Input validation middleware
│       └── logging.py          # Request/response logging
```

### 6. Utilities and Setup
```
src/
├── utils/
│   ├── __init__.py
│   ├── embeddings.py          # OpenAI embedding utilities
│   ├── citations.py           # Legal citation parsing
│   ├── validators.py          # Input validation utilities
│   ├── formatters.py          # Response formatting utilities
│   └── text_processing.py     # Text processing utilities
├── setup/
│   ├── __init__.py
│   ├── database_setup.py      # Database initialization
│   ├── migrations.py          # Database migrations
│   └── fixtures.py            # Test data fixtures
```

### 7. Configuration and Entry Points
```
├── config/
│   ├── __init__.py
│   ├── development.py         # Development configuration
│   ├── production.py          # Production configuration
│   └── testing.py             # Testing configuration
├── main.py                    # Entry point (much smaller ~50 lines)
├── setup.py                   # Setup script
├── cli.py                     # CLI interface (optional)
```

### 8. Testing Structure
```
tests/
├── __init__.py
├── conftest.py                # Pytest configuration and fixtures
├── unit/
│   ├── services/              # Service unit tests
│   ├── tools/                 # Tool unit tests
│   └── utils/                 # Utility unit tests
├── integration/
│   ├── database/              # Database integration tests
│   ├── mcp/                   # MCP server integration tests
│   └── external/              # External service integration tests
└── fixtures/
    ├── legal_data.py          # Legal test data
    └── mock_responses.py      # Mock API responses
```

## 🔧 Implementation Benefits

### 1. **Separation of Concerns**
- **Models**: Pure data structures with validation
- **Services**: Business logic isolated from MCP interface
- **Tools**: Thin wrappers that call services
- **Database**: Isolated data access layer

### 2. **Testability**
```python
# Example: Easy to unit test services
def test_event_service_create():
    service = EventService(mock_database)
    result = service.create_event(event_data)
    assert result.status == "success"

# Example: Easy to test tools with mocked services
def test_add_event_tool():
    mock_service = Mock()
    tool = AddEventTool(mock_service)
    result = await tool.execute(event_data)
    mock_service.create_event.assert_called_once()
```

### 3. **Configuration Management**
```python
# config/base.py
@dataclass
class DatabaseConfig:
    postgres_url: str
    qdrant_url: str
    neo4j_uri: str

@dataclass
class SueChefConfig:
    database: DatabaseConfig
    openai_api_key: str
    environment: str = "development"
```

### 4. **Dependency Injection**
```python
# services/base.py
class BaseService:
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager

# tools/base.py
class BaseTool:
    def __init__(self, service: BaseService):
        self.service = service
```

### 5. **Plugin Architecture**
```python
# tools/registry.py
class ToolRegistry:
    def __init__(self):
        self._tools = {}
    
    def register(self, tool_class):
        self._tools[tool_class.name] = tool_class
    
    def auto_discover(self, package):
        # Automatically discover and register tools
        pass
```

## 📋 Migration Strategy

### Phase 1: Foundation (Week 1)
1. **Extract Configuration**
   - Create `src/core/config.py`
   - Centralize environment variable handling
   - Add configuration validation

2. **Database Layer**
   - Extract database clients to `src/core/database/`
   - Create connection manager
   - Implement proper lifecycle management

### Phase 2: Services (Week 2)
1. **Extract Business Logic**
   - Create service layer for events, snippets, search
   - Move business logic from tools to services
   - Add service interfaces/contracts

2. **Testing Foundation**
   - Set up pytest configuration
   - Create test fixtures
   - Add unit tests for services

### Phase 3: Tools Modularization (Week 3)
1. **Break Up Large Files**
   - Split `legal_tools.py` by domain
   - Create tool base classes
   - Implement tool registry

2. **MCP Layer**
   - Extract resources and prompts
   - Simplify main server file
   - Add middleware layer

### Phase 4: Polish & Documentation (Week 4)
1. **Documentation**
   - Update README with new structure
   - Add developer documentation
   - Create contribution guidelines

2. **Performance & Monitoring**
   - Add performance monitoring
   - Implement proper logging
   - Add health checks

## 🎯 Example: Modularized Event Tool

### Before (current):
```python
# In main.py (656 lines)
@mcp.tool()
async def add_event(date, description, ...):
    await ensure_initialized()
    return await legal_tools.add_event(
        postgres_pool, qdrant_client, graphiti_client, ...
    )
```

### After (modularized):
```python
# src/tools/legal/events/crud_tools.py
class AddEventTool(BaseTool):
    def __init__(self, event_service: EventService):
        self.event_service = event_service
    
    @tool()
    async def add_event(self, request: CreateEventRequest) -> EventResponse:
        return await self.event_service.create_event(request)

# src/services/legal/event_service.py
class EventService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    async def create_event(self, request: CreateEventRequest) -> EventResponse:
        # Business logic here
        pass

# main.py (now ~50 lines)
async def main():
    config = load_config()
    db_manager = DatabaseManager(config.database)
    
    # Auto-register tools
    registry = ToolRegistry()
    registry.auto_discover("src.tools")
    
    server = MCPServer(config, registry)
    await server.start()
```

## 📈 Expected Outcomes

### 1. **Maintainability**
- **80% reduction** in main.py size (656 → ~50 lines)
- **60% reduction** in largest file size through domain splitting
- Clear responsibility boundaries

### 2. **Testability**
- **100% unit test coverage** achievable with isolated components
- **Fast test execution** with mocked dependencies
- **Integration tests** for critical paths

### 3. **Developer Experience**
- **Easy feature addition** through plugin architecture
- **Clear contribution guidelines** with modular structure
- **Better IDE support** with smaller, focused files

### 4. **Scalability**
- **Easy horizontal scaling** of individual services
- **Feature flags** and conditional loading
- **Multiple interface support** (MCP, REST API, CLI)

## 🚀 Getting Started

Would you like to begin with **Phase 1** (Foundation) by extracting the configuration and database layers? This would provide immediate benefits while maintaining backward compatibility.

The modularization can be done incrementally, ensuring the system remains functional throughout the process.