# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a unified-legal-mcp project built with Python 3.12+ and FastMCP framework. It provides a comprehensive legal research system combining PostgreSQL, Qdrant vector database, and Graphiti knowledge graphs for intelligent legal data management and analysis.

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
- `database_schema.py` - PostgreSQL schema and Qdrant collection definitions
- `setup.py` - Database initialization script
- `pyproject.toml` - Project configuration and dependencies
- `uv.lock` - Lock file for reproducible builds

## Development Notes

This is a Model Context Protocol (MCP) server project using FastMCP for legal research. When developing:
- FastMCP is used for building MCP servers that can integrate with AI assistants
- The project is configured for Python 3.12 or higher
- Use `uv` for all package management operations to maintain consistency
- The system combines three databases: PostgreSQL for structured data, Qdrant for vector search, and Neo4j/Graphiti for knowledge graphs
- All tools are async and support concurrent operations
- OpenAI API key is required for generating embeddings

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

## Dependency Management Guidelines
- Use `uv` to manage python dependencies, builds, etc. 
- Do not manually edit project config or dependency files

## Database
- Use `qdrant` for vector database
- Use `postgres` for standard relational data

## Knowledge Graphs
- Use `graphiti` and `neo4j` for knowledge graphs