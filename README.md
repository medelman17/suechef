<p align="center">
  <img src="https://raw.githubusercontent.com/fortai-legal/suechef/main/media/logo.png" alt="SueChef Logo" width="400">
</p>

<h1 align="center">SueChef - Legal Research MCP</h1>

<p align="center">
  <em>Your AI sous chef for cooking up winning legal strategies</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#architecture--the-suechef-kitchen-">Architecture</a> •
  <a href="#license">License</a>
</p>

---

SueChef is a powerful legal research MCP (Model Context Protocol) that combines PostgreSQL, Qdrant vector database, and Graphiti knowledge graphs to help you prepare the perfect legal case - with all the right ingredients!

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

### ⚖️ CourtListener Integration
- **search_courtlistener_opinions**: Search millions of court opinions by query, court, date, and citation count
- **import_courtlistener_opinion**: Import opinions as snippets with automatic event linking
- **search_courtlistener_dockets**: Find active cases, parties, and procedural history
- **find_citing_opinions**: Discover all cases that cite a specific precedent
- **analyze_courtlistener_precedents**: Analyze how legal precedents evolved over decades

## Prerequisites

- Python 3.12+
- PostgreSQL
- Qdrant vector database
- Neo4j graph database
- OpenAI API key (for embeddings)
- CourtListener API key (optional, for enhanced access)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/medelman17/suechef.git
cd suechef
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
export COURTLISTENER_API_KEY="your-courtlistener-api-key"  # Optional
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

### CourtListener Integration Example

```python
# 1. Search for relevant precedents
opinions = search_courtlistener_opinions(
    query="landlord liability water damage notice",
    court="ca9",  # Ninth Circuit
    cited_gt=10,  # Well-cited cases
    date_after="2000-01-01"
)

# 2. Import a key precedent
import_courtlistener_opinion(
    opinion_id=12345,
    add_as_snippet=True,
    auto_link_events=True
)

# 3. Find cases that cite your precedent
citing_cases = find_citing_opinions(
    citation="Johnson v. Property Mgmt Co., 123 F.3d 456"
)

# 4. Analyze precedent evolution
analysis = analyze_courtlistener_precedents(
    topic="landlord liability water damage",
    jurisdiction="ca9",
    date_range_years=30
)

# 5. Search active litigation
dockets = search_courtlistener_dockets(
    case_name="tenant water damage",
    date_filed_after="2020-01-01"
)
```

## Architecture - The SueChef Kitchen 🍳

SueChef's kitchen uses three complementary technologies to serve up legal insights:

1. **PostgreSQL** (The Pantry): Structured data storage with JSONB support for flexible schemas and full-text search capabilities
2. **Qdrant** (The Spice Rack): Vector database for semantic search using OpenAI embeddings - finding the perfect flavor matches
3. **Graphiti + Neo4j** (The Recipe Book): Knowledge graph for entity extraction and relationship mapping - understanding how ingredients work together

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