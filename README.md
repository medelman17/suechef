# Unified Legal MCP (Model Context Protocol)

A powerful legal research system that combines PostgreSQL, Qdrant vector database, and Graphiti knowledge graphs to provide comprehensive legal intelligence and research capabilities.

## Features

### =� Timeline & Event Management
- **add_event**: Add chronology events with automatic vector and knowledge graph storage
- **get_event**: Get a single event by ID
- **list_events**: List events with filtering by date, parties, or tags
- **update_event**: Update existing event (partial updates supported)
- **delete_event**: Delete an event from all systems
- **create_snippet**: Create legal research snippets (case law, precedents, statutes)
- **get_snippet**: Get a single snippet by ID
- **list_snippets**: List snippets with filtering by case type or tags
- **update_snippet**: Update existing snippet (partial updates supported)
- **delete_snippet**: Delete a snippet from all systems

### = Search & Discovery
- **unified_legal_search**: Hybrid search across PostgreSQL + Qdrant + Graphiti
- **postgres_full_text_search**: Advanced PostgreSQL full-text search with relevance ranking
- **postgres_advanced_query**: Execute complex PostgreSQL queries with JSONB operations

### =� Document Processing
- **ingest_legal_document**: Feed entire legal documents for automatic entity extraction and knowledge graph building

### =p Temporal Intelligence
- **temporal_legal_query**: Ask temporal questions about legal knowledge evolution

### = Relationship Management
- **create_manual_link**: Create explicit relationships between events and legal precedents

### =� Analytics & Insights
- **get_legal_analytics**: Comprehensive legal research analytics
- **get_system_status**: Health check for all system components

## Prerequisites

- Python 3.12+
- PostgreSQL
- Qdrant vector database
- Neo4j graph database
- OpenAI API key (for embeddings)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/medelman17/unified-legal-mcp.git
cd unified-legal-mcp
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Set up environment variables:
```bash
export POSTGRES_URL="postgresql://localhost/legal_research"
export QDRANT_URL="http://localhost:6333"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="your-password"
export OPENAI_API_KEY="your-openai-api-key"
```

4. Run the setup script:
```bash
uv run python setup.py
```

## Usage

### Running the MCP Server

```bash
uv run python main.py
```

### Example Workflow

```python
# 1. Ingest legal documents
ingest_legal_document(
    document_text="Full text of court filing...",
    title="Smith v. Landlord Corp (1995)",
    date="1995-03-15",
    document_type="court_filing"
)

# 2. Build detailed timeline
add_event(
    date="2023-05-14",
    description="Tenant reports flooding to property management",
    parties=["John Smith", "Property Management LLC"],
    document_source="Email correspondence",
    tags=["water damage", "notice", "maintenance"],
    significance="First documented notice of water damage"
)

# 3. Add legal precedents
create_snippet(
    citation="Johnson v. Property Mgmt Co., 123 F.3d 456 (2010)",
    key_language="Landlord has duty to repair once on notice of defects",
    tags=["landlord liability", "notice", "duty to repair"],
    case_type="premises liability"
)

# 4. Search for related content
unified_legal_search(
    query="landlord knowledge of defects water damage",
    search_type="all"
)

# 5. Analyze temporal patterns
temporal_legal_query(
    question="How has landlord liability for water damage evolved?",
    time_focus="1995-2023",
    entity_focus="premises liability"
)

# 6. Get analytics
get_legal_analytics()
```

## Architecture

The system uses three complementary technologies:

1. **PostgreSQL**: Structured data storage with JSONB support for flexible schemas and full-text search capabilities
2. **Qdrant**: Vector database for semantic search using OpenAI embeddings
3. **Graphiti + Neo4j**: Knowledge graph for entity extraction and relationship mapping

## Development

### Adding Dependencies
```bash
uv add <package-name>
```

### Running Tests
```bash
uv run pytest
```

## License

MIT License