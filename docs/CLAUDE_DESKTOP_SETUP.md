# SueChef + Claude Desktop Integration Guide

Connect your SueChef legal research MCP server to Claude Desktop for enhanced AI-powered legal analysis with access to all 26 specialized legal tools.

## 🎯 What You'll Get

Once configured, Claude Desktop will have direct access to:
- **Timeline Management**: Add, search, and analyze legal events and chronologies
- **Legal Research**: Create and search legal snippets, precedents, and case law
- **Vector Search**: Semantic search across legal documents using AI embeddings
- **Knowledge Graphs**: Temporal legal knowledge with entity extraction and relationships
- **CourtListener Integration**: Search millions of court opinions and active cases
- **Legal Analytics**: Comprehensive legal research analytics and insights
- **Community Detection**: Identify clusters of related legal concepts

## 📋 Prerequisites

- **Claude Desktop**: Download from [claude.ai/desktop](https://claude.ai/desktop)
- **SueChef Running**: Either locally or via Docker
- **API Keys**: OpenAI API key (required), CourtListener API key (optional)

## 🚀 Quick Setup (Recommended)

### 1. Start SueChef with Docker

```bash
# Clone the repository
git clone https://github.com/medelman17/suechef.git
cd suechef

# Set up environment variables
export OPENAI_API_KEY="your-openai-api-key"
export COURTLISTENER_API_KEY="your-courtlistener-api-key"  # optional

# Start all services (now uses modular architecture by default)
docker compose up -d

# Verify SueChef is running
curl http://localhost:8000/mcp
# Should return MCP session information
```

### 2. Configure Claude Desktop (Two Options)

#### Option A: Pre-configured Setup (Easiest)
```bash
# Copy the included MCP configuration
cp /path/to/suechef/.mcp.json ~/.config/claude-desktop/mcp.json

# Set your API keys
export OPENAI_API_KEY="your-openai-api-key"
export COURTLISTENER_API_KEY="your-courtlistener-api-key"
```

#### Option B: Manual Configuration
**On macOS**: Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
**On Windows**: Edit `%APPDATA%/Claude/claude_desktop_config.json`
**On Linux**: Edit `~/.config/claude-desktop/mcp.json`

```json
{
  "mcpServers": {
    "suechef": {
      "command": "uv",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/suechef",
      "env": {
        "POSTGRES_URL": "postgresql://postgres:suechef_password@localhost:5432/legal_research",
        "QDRANT_URL": "http://localhost:6333",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "suechef_neo4j_password",
        "OPENAI_API_KEY": "your-openai-api-key",
        "COURTLISTENER_API_KEY": "your-courtlistener-api-key"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

Close and reopen Claude Desktop. You should see SueChef tools appear in the interface.

## 🏗️ Alternative Setup Options

### Option A: Local Development Setup

If you're developing or want to run SueChef locally without Docker:

```bash
# Install dependencies
uv sync

# Start only the databases with Docker
docker compose up postgres qdrant neo4j -d

# Set environment variables
export OPENAI_API_KEY="your-openai-key"
export POSTGRES_URL="postgresql://postgres:suechef_password@localhost:5432/legal_research"
export QDRANT_URL="http://localhost:6333"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="suechef_neo4j_password"

# Start SueChef (modular architecture)
uv run python main.py
```

### Option B: Legacy Architecture (Reference Only)

If you need to test the legacy implementation:

```bash
# Start with legacy version
uv run python main_legacy.py
```

Note: The legacy version is preserved for reference but the modular architecture is recommended for all new deployments.

### Option C: Custom Port Configuration

If you need to run on a different port:

```bash
# Start with custom port
docker-compose up -d
# Edit docker-compose.yml to change port mapping from "8000:8000" to "9000:8000"
```

Claude Desktop configuration:
```json
{
  "mcpServers": {
    "suechef": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://localhost:9000/mcp"],
      "env": {}
    }
  }
}
```

## 🔧 Advanced Configuration

### Multiple Environments

You can configure different SueChef instances for different cases or clients:

```json
{
  "mcpServers": {
    "suechef-personal": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://localhost:8000/mcp"],
      "env": {}
    },
    "suechef-work": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://work-server:8000/mcp"],
      "env": {}
    }
  }
}
```

### With Authentication (Future)

When SueChef adds authentication support:

```json
{
  "mcpServers": {
    "suechef": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-client", "http://localhost:8000/mcp"],
      "env": {
        "SUECHEF_API_KEY": "your-api-key"
      }
    }
  }
}
```

## 🧪 Testing the Integration

### 1. Verify Connection

Ask Claude Desktop:
```
Are SueChef tools available? Can you show me what legal research tools you have access to?
```

Claude should respond with a list of 26+ legal tools including events, snippets, search, and CourtListener integration.

### 2. Test Basic Functionality

```
Can you add a legal event to my timeline for "2024-01-15" with description "Lease agreement signed with ABC Properties"?
```

### 3. Test Search Capabilities

```
Search for legal precedents related to "landlord liability water damage" using SueChef's unified search.
```

### 4. Test Analytics

```
Can you get a summary of my legal research analytics using SueChef?
```

## 🎯 Example Workflows

### Workflow 1: Case Timeline Development

```
I'm working on a premises liability case. Can you help me:

1. Add an event for the initial incident on 2023-05-14
2. Add when notice was given to the landlord on 2023-05-16  
3. Search for similar precedents about landlord liability
4. Import any relevant court opinions from CourtListener
5. Create a timeline analysis of the case development
```

### Workflow 2: Legal Research Session

```
I need to research "breach of contract remedies" in California. Can you:

1. Search CourtListener for recent California cases
2. Create legal snippets for the most relevant precedents
3. Search for related legal concepts using community detection
4. Analyze how contract remedy law has evolved over time
5. Generate a comprehensive research report
```

### Workflow 3: Document Analysis

```
I have a complex legal document I need to analyze. Can you:

1. Ingest the document into SueChef's knowledge graph
2. Extract key legal entities and relationships
3. Find related precedents and case law
4. Create timeline events for important dates mentioned
5. Generate insights about potential legal issues
```

## 🔍 Troubleshooting

### SueChef Not Appearing in Claude Desktop

1. **Check SueChef is running**:
   ```bash
   curl http://localhost:8000/mcp
   ```

2. **Verify configuration file location**:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%/Claude/claude_desktop_config.json`

3. **Check JSON syntax**:
   Use a JSON validator to ensure your config file is valid.

4. **Restart Claude Desktop completely**:
   Quit the application entirely and restart.

### Connection Errors

1. **Port conflicts**: Ensure port 8000 isn't used by another service
2. **Firewall issues**: Check that localhost connections are allowed
3. **Docker issues**: Verify all containers are healthy:
   ```bash
   docker-compose ps
   ```

### Tool Execution Errors

1. **Missing API keys**: Ensure `OPENAI_API_KEY` is set in your `.env` file
2. **Database not initialized**: Run the setup script:
   ```bash
   uv run python setup.py
   ```

3. **Check logs**:
   ```bash
   docker-compose logs suechef
   ```

## 📚 Advanced Features

### Group-Based Data Isolation

SueChef supports multi-tenant data isolation using `group_id` parameters:

```
Add an event to the "johnson-case" group for better organization of different legal matters.
```

### Custom Entity Types

SueChef uses specialized legal entity types (Judge, Attorney, Court, etc.) for enhanced knowledge representation:

```
Search for information about judges in the Ninth Circuit and analyze their judicial philosophy patterns.
```

### Temporal Legal Analysis

Ask complex temporal questions:

```
How has landlord liability law evolved in California over the past 20 years? Use SueChef's temporal analysis capabilities.
```

## 🚀 Next Steps

Once SueChef is integrated with Claude Desktop:

1. **Explore all 26 tools** - Ask Claude to demonstrate different capabilities
2. **Set up your first case** - Create events, add precedents, build timelines
3. **Import CourtListener data** - Access millions of court opinions
4. **Use community detection** - Find related legal concepts automatically
5. **Generate analytics** - Get insights into your legal research patterns

## 📞 Support

- **Documentation**: See `README.md` for comprehensive setup instructions
- **Architecture**: See `MODULARIZATION_PROPOSAL.md` for technical details
- **Issues**: Report problems at [GitHub Issues](https://github.com/medelman17/suechef/issues)
- **Updates**: Watch the repository for new features and improvements

---

**Ready to supercharge your legal research with AI? Start cooking up winning legal strategies with SueChef! 🍳⚖️**