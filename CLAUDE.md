# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SueChef is a legal research MCP (Model Context Protocol) built with Python 3.12+ and FastMCP framework. The name is a play on "sous chef" - it's your AI assistant for cooking up winning legal strategies! 👨‍🍳⚖️

SueChef provides a comprehensive legal research system combining PostgreSQL, Qdrant vector database, and Graphiti knowledge graphs for intelligent legal data management and analysis.

## Development Environment

### Package Management
This project uses `uv` as the package manager. The virtual environment is located at `.venv/`.

### Key Dependencies
- FastMCP >= 2.5.2 (for building Model Context Protocol servers)
- Python >= 3.12
- PostgreSQL (asyncpg, psycopg2-binary, sqlalchemy)
- Qdrant (qdrant-client)
- Neo4j (neo4j, graphiti-core)
- OpenAI (for embeddings)
- eyecite (legal citation parsing)

## Common Commands

### Install dependencies
```bash
uv sync
```

### Run the application
```bash
uv run python main.py
```

### Run setup (initialize databases)
```bash
uv run python setup.py
```

### Add a new dependency
```bash
uv add <package-name>
```

### Remove a dependency
```bash
uv remove <package-name>
```

## Project Structure

- `main.py` - FastMCP server implementation with tool routing
- `legal_tools.py` - Implementation of all legal research tools
- `legal_entity_types.py` - Custom Pydantic models for legal domain entities
- `database_schema.py` - PostgreSQL schema and Qdrant collection definitions
- `setup.py` - Database initialization script
- `pyproject.toml` - Project configuration and dependencies
- `uv.lock` - Lock file for reproducible builds

## Development Notes

SueChef is a Model Context Protocol (MCP) server project using FastMCP for legal research. When developing:
- FastMCP is used for building MCP servers that can integrate with AI assistants
- The project is configured for Python 3.12 or higher
- Use `uv` for all package management operations to maintain consistency
- The system combines three databases: PostgreSQL for structured data, Qdrant for vector search, and Neo4j/Graphiti for knowledge graphs
- All tools are async and support concurrent operations
- OpenAI API key is required for generating embeddings
- **Group-based namespacing** enables multi-client/matter data isolation using `group_id` parameters
- **Custom entity types** provide precise legal domain modeling with Pydantic schemas
- **Community detection** identifies clusters of related legal concepts and precedents

### Available Tools

**Event Management:**
1. **add_event** - Add chronology events
2. **get_event** - Get a single event by ID
3. **list_events** - List events with filtering
4. **update_event** - Update existing event
5. **delete_event** - Delete an event

**Snippet Management:**
6. **create_snippet** - Create legal research snippets
7. **get_snippet** - Get a single snippet by ID
8. **list_snippets** - List snippets with filtering
9. **update_snippet** - Update existing snippet
10. **delete_snippet** - Delete a snippet

**Search & Analysis:**
11. **unified_legal_search** - Hybrid search across all systems
12. **postgres_full_text_search** - PostgreSQL full-text search
13. **postgres_advanced_query** - Complex JSONB queries
14. **temporal_legal_query** - Temporal knowledge queries

**Document & Relationship Management:**
15. **ingest_legal_document** - Process full documents
16. **create_manual_link** - Link events to precedents

**System:**
17. **get_legal_analytics** - Comprehensive analytics
18. **get_system_status** - Health check

**CourtListener Integration:**
19. **search_courtlistener_opinions** - Search court opinions
20. **import_courtlistener_opinion** - Import opinions as snippets
21. **search_courtlistener_dockets** - Search active cases
22. **find_citing_opinions** - Find cases citing a precedent
23. **analyze_courtlistener_precedents** - Analyze precedent evolution

**Advanced Knowledge Graph Features:**
24. **build_legal_communities** - Build communities to identify legal concept clusters
25. **search_legal_communities** - Search for communities related to legal queries
26. **enhanced_legal_search** - Configurable search with SearchConfig for nodes/edges/communities

## Dependency Management Guidelines
- Use `uv` to manage python dependencies, builds, etc. 
- Do not manually edit project config or dependency files

## Database
- Use `qdrant` for vector database
- Use `postgres` for standard relational data

## Knowledge Graphs
- Use `graphiti` and `neo4j` for knowledge graphs

## Advanced Features

### Custom Entity Types
SueChef uses custom Pydantic models to define legal domain entities for precise knowledge representation:
- **Judge** - Judicial officers with appointment dates, courts, political affiliations
- **Attorney** - Legal practitioners with firm affiliations, bar numbers, specializations
- **Court** - Judicial venues with jurisdictions, levels, circuit information
- **LegalCase** - Legal proceedings with case numbers, filing dates, status
- **Statute** - Laws and regulations with citations, jurisdictions, effective dates
- **LegalPrecedent** - Case law with holdings, precedential value, overturn status
- **Evidence** - Documentary, physical, or testimonial evidence with admissibility status
- **Claim** - Legal causes of action with required elements and burdens of proof
- **Contract** - Legal agreements with parties, terms, governing law

### Group-Based Namespacing
All data operations support `group_id` parameters for multi-tenant isolation:
- Separate different legal matters, clients, or case files
- Filter searches and analytics by group
- Maintain data privacy and organization
- Default group is "default" if not specified

### Community Detection
Graphiti-powered community detection identifies related legal concepts:
- Automatically cluster related cases, precedents, and legal concepts
- Generate summaries for community overviews
- Filter communities by group for client-specific analysis
- Use community search for high-level legal topic exploration

### Enhanced Search Capabilities
Configurable search with multiple focus areas:
- **Hybrid Search** - Balanced retrieval across nodes, edges, and communities
- **Node-Focused** - Entity-centric search (judges, courts, cases)
- **Edge-Focused** - Relationship-centric search (citations, precedent chains)
- **Community-Focused** - Topic cluster search (legal concept areas)
- All searches support group filtering and custom limits