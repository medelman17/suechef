<p align="center">
  <img src="media/suecheflogo.png" alt="SueChef Logo" width="400">
</p>

<h1 align="center">SueChef - Legal Research MCP</h1>

<p align="center">
  <em>Your AI sous chef for cooking up winning legal strategies</em>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start-with-docker">Quick Start</a> •
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

### 🧠 Advanced Knowledge Graph Features
- **build_legal_communities**: Build communities to identify legal concept clusters
- **search_legal_communities**: Search for communities related to legal queries
- **enhanced_legal_search**: Configurable search with SearchConfig for nodes/edges/communities

## Quick Start with Docker

The fastest way to get SueChef running is with Docker Compose:

### 1. Clone and Setup
```bash
git clone https://github.com/medelman17/suechef.git
cd suechef
cp .env.example .env
# Edit .env with your OpenAI API key
```

### 2. Start Services
```bash
# Start just the databases (recommended for development)
docker-compose up -d

# Or start everything including SueChef MCP server
docker-compose --profile full up -d
```

### 3. Initialize Database
```bash
# Run setup script to create schemas
uv run python setup.py
```

### 4. Access Services
- **PostgreSQL**: `localhost:5432` (user: postgres, password: suechef_password)
- **Qdrant**: `http://localhost:6333` (dashboard at `/dashboard`)
- **Neo4j**: `http://localhost:7474` (user: neo4j, password: suechef_neo4j_password)
- **SueChef MCP**: `localhost:8000` (if using --profile full)

### 5. Stop Services
```bash
docker-compose down
# Add -v to remove volumes and reset data
docker-compose down -v
```

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (for quick setup)
- OpenAI API key (for embeddings)
- CourtListener API key (optional, for enhanced access)

## Installation

### Option 1: Docker (Recommended)
Follow the [Quick Start](#quick-start-with-docker) above.

### Option 2: Local Development
1. Clone the repository:
```bash
git clone https://github.com/medelman17/suechef.git
cd suechef
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Set up local databases:
   - Install PostgreSQL, Qdrant, and Neo4j locally
   - Or use Docker for databases only: `docker-compose up -d postgres qdrant neo4j`

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run the setup script:
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

### Docker Development
```bash
# Rebuild after code changes
docker-compose build suechef

# View logs
docker-compose logs -f suechef

# Access running container
docker-compose exec suechef bash
```

## License

MIT License