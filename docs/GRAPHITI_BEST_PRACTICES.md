# Graphiti Best Practices for SueChef

This document outlines the best practices for using Graphiti in the SueChef legal research MCP based on comprehensive research of the graphiti-core package.

## Table of Contents
1. [Correct Import Patterns](#correct-import-patterns)
2. [Proper Initialization](#proper-initialization)
3. [Episode Management](#episode-management)
4. [Search Operations](#search-operations)
5. [Community Detection](#community-detection)
6. [Error Handling](#error-handling)
7. [Common Pitfalls](#common-pitfalls)
8. [Migration Guide](#migration-guide)

## Correct Import Patterns

### ✅ Correct Imports
```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType
from graphiti_core.search.search_config_recipes import (
    COMBINED_HYBRID_SEARCH_RRF,
    NODE_HYBRID_SEARCH_RRF,
    EDGE_HYBRID_SEARCH_RRF,
    COMMUNITY_HYBRID_SEARCH_RRF
)
```

### ❌ Incorrect Imports (Avoid These)
```python
# These are internal classes and may not be publicly available
from graphiti_core.nodes import EntityNode, EpisodeNode

# SearchConfig should use recipes, not direct import
from graphiti_core.search import SearchConfig
```

## Proper Initialization

### ✅ Correct Initialization Pattern
```python
async def initialize_graphiti():
    """Proper Graphiti initialization."""
    graphiti_client = Graphiti(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password")
    )
    
    # CRITICAL: Build indices and constraints after initialization
    await graphiti_client.build_indices_and_constraints()
    
    return graphiti_client
```

### ❌ Incorrect Initialization (Current SueChef Issue)
```python
# Wrong parameter names and missing constraints setup
graphiti_client = Graphiti(
    neo4j_driver=neo4j_driver,  # Wrong parameter
    openai_api_key=api_key      # Should use environment variable
)
# Missing: await graphiti_client.build_indices_and_constraints()
```

## Episode Management

### ✅ Correct Episode Addition
```python
async def add_legal_episode(graphiti_client, event_data, group_id="default"):
    """Add a legal episode with proper parameters."""
    
    # Format episode content
    episode_content = f"""
    Date: {event_data['date']}
    Description: {event_data['description']}
    Parties: {', '.join(event_data.get('parties', []))}
    Significance: {event_data.get('significance', 'N/A')}
    """
    
    await graphiti_client.add_episode(
        name=f"Legal Event - {event_data['date']}",
        episode_body=episode_content,  # NOT 'content'
        source=EpisodeType.text,       # Use EpisodeType enum
        source_description="Legal Timeline Entry",
        reference_time=datetime.strptime(event_data['date'], "%Y-%m-%d"),
        group_id=group_id  # Pass as kwargs if supported
    )
```

### ❌ Incorrect Episode Addition (Current SueChef Issue)
```python
# Wrong parameter names and unsupported parameters
await graphiti_client.add_episode(
    content=episode_content,           # Wrong - use 'episode_body'
    source="Legal Timeline",           # Wrong - use EpisodeType.text
    entity_types=LITIGATION_ENTITIES,  # Wrong - not supported
    group_id=group_id
)
```

## Search Operations

### ✅ Correct Search Patterns

#### Basic Search
```python
async def basic_legal_search(graphiti_client, query, group_id=None):
    """Basic search with group filtering."""
    group_ids = [group_id] if group_id else None
    
    results = await graphiti_client.search(
        query=query,
        group_ids=group_ids,
        num_results=20
    )
    return results
```

#### Advanced Search with Configurations
```python
async def enhanced_legal_search(graphiti_client, query, search_focus="hybrid"):
    """Enhanced search using predefined search configurations."""
    
    # Select appropriate search recipe
    config_map = {
        "nodes": NODE_HYBRID_SEARCH_RRF,
        "edges": EDGE_HYBRID_SEARCH_RRF,
        "communities": COMMUNITY_HYBRID_SEARCH_RRF,
        "hybrid": COMBINED_HYBRID_SEARCH_RRF
    }
    
    config = config_map.get(search_focus, COMBINED_HYBRID_SEARCH_RRF)
    
    # Use _search method for advanced configurations
    results = await graphiti_client._search(
        query=query,
        config=config
    )
    return results
```

### ❌ Incorrect Search (Current SueChef Issue)
```python
# Manual SearchConfig creation - not supported
search_config = SearchConfig(
    limit=limit,
    communities_config={"enabled": True}
)
```

## Community Detection

### ✅ Correct Community Operations
```python
async def build_legal_communities(graphiti_client, group_id=None):
    """Build communities with proper group handling."""
    group_ids = [group_id] if group_id else None
    
    await graphiti_client.build_communities(group_ids=group_ids)
    
    return {"status": "success", "message": "Communities built successfully"}

async def search_legal_communities(graphiti_client, query, group_id=None):
    """Search communities using proper configuration."""
    # Communities are searched via advanced search
    results = await graphiti_client._search(
        query=query,
        config=COMMUNITY_HYBRID_SEARCH_RRF
    )
    
    # Filter by group if needed (manual filtering may be required)
    if group_id:
        # Implement group filtering logic based on result structure
        pass
    
    return results
```

## Error Handling

### ✅ Proper Error Handling
```python
async def safe_graphiti_operation(graphiti_client, operation_func, *args, **kwargs):
    """Wrapper for safe Graphiti operations."""
    try:
        result = await operation_func(graphiti_client, *args, **kwargs)
        return {"status": "success", "data": result}
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Graphiti operation failed: {str(e)}",
            "error_type": type(e).__name__
        }

async def graceful_shutdown(graphiti_client):
    """Properly close Graphiti connection."""
    try:
        await graphiti_client.close()
    except Exception as e:
        print(f"Error closing Graphiti client: {e}")
```

## Common Pitfalls

### 1. Parameter Naming
- ❌ `content` → ✅ `episode_body`
- ❌ `source="string"` → ✅ `source=EpisodeType.text`
- ❌ `group_id="string"` → ✅ `group_ids=["string"]`

### 2. Initialization Issues
- ❌ Forgetting `build_indices_and_constraints()`
- ❌ Using wrong constructor parameters
- ❌ Not handling async properly

### 3. Search Configuration
- ❌ Creating manual `SearchConfig` objects
- ✅ Using predefined search recipes

### 4. Entity Types
- ❌ Passing `entity_types` to `add_episode()`
- ✅ Let Graphiti handle entity extraction automatically

### 5. Group Management
- ❌ Passing single string for group filtering
- ✅ Pass list of strings: `group_ids=[group_id]`

## Migration Guide

### From Current SueChef Implementation

1. **Fix Imports**
   ```python
   # Remove these imports
   # from graphiti_core.nodes import EntityNode, EpisodeNode
   
   # Add these imports
   from graphiti_core.nodes import EpisodeType
   from graphiti_core.search.search_config_recipes import *
   ```

2. **Fix Initialization**
   ```python
   # Change from:
   graphiti_client = Graphiti(neo4j_driver=driver, openai_api_key=key)
   
   # To:
   graphiti_client = Graphiti(uri=uri, user=user, password=password)
   await graphiti_client.build_indices_and_constraints()
   ```

3. **Fix Episode Addition**
   ```python
   # Change from:
   await graphiti_client.add_episode(
       content=text,
       entity_types=types,
       group_id=group
   )
   
   # To:
   await graphiti_client.add_episode(
       name="Episode Name",
       episode_body=text,
       source=EpisodeType.text,
       source_description="Source description",
       reference_time=datetime.now(timezone.utc),
       group_id=group
   )
   ```

4. **Fix Search Operations**
   ```python
   # Change from manual SearchConfig to recipes
   # Replace custom SearchConfig with:
   from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
   
   results = await graphiti_client._search(query=query, config=COMBINED_HYBRID_SEARCH_RRF)
   ```

## Version Compatibility

- **Recommended**: `graphiti-core>=0.11.6` (latest)
- **API Breaking Changes**: Significant changes between 0.10.x and 0.11.x
- **Environment**: Python 3.12+ recommended
- **Dependencies**: Ensure Neo4j 5.x compatibility

## Testing and Debugging

### Health Check Pattern
```python
async def test_graphiti_health(graphiti_client):
    """Test Graphiti connectivity and basic operations."""
    try:
        # Test basic search
        results = await graphiti_client.search("test", num_results=1)
        return {"status": "healthy", "connection": "ok"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### Debug Logging
```python
import logging

# Enable Graphiti debug logging
logging.getLogger("graphiti").setLevel(logging.DEBUG)
```

---

**Last Updated**: January 2025  
**Graphiti Version**: 0.11.6+  
**Applicable To**: SueChef Legal Research MCP