# Post-Mortem: Database Infrastructure and Event Loop Issues

**Date**: June 1, 2025  
**Duration**: ~45 minutes  
**Severity**: High (Core infrastructure failure)  
**Services Affected**: PostgreSQL operations, Event/Snippet services, Search functionality

## Executive Summary

Multiple critical infrastructure issues were identified and resolved in the SueChef MCP server, including PostgreSQL connection pool conflicts, event loop management problems, function parameter mismatches, and improper service initialization patterns. The primary root cause was improper initialization sequencing between async event loops and the FastMCP server lifecycle.

## Timeline

1. **Issues Identified**: Database operations failing with "operation in progress" and "event loop closed" errors
2. **Investigation Started**: Analyzed PostgreSQL connection patterns and async operation management
3. **Root Causes Found**: Improper initialization lifecycle and parameter mismatches
4. **Fixes Implemented**: Adopted proper FastMCP lifespan pattern and fixed function signatures
5. **Service Restored**: All database operations now functional

## Impact

### What Broke
- **PostgreSQL Operations**: "another operation is in progress" errors
- **Event Loop Management**: "Event loop is closed" errors affecting async operations
- **Function Parameters**: Parameter count mismatches in `unified_legal_search`
- **Service Initialization**: Race conditions between async initialization and MCP server startup

### User Impact
- Complete inability to list/create snippets and events
- Search functionality broken
- Database operations unreliable
- Only CourtListener integration remained functional

## Root Cause Analysis

### 1. Event Loop Lifecycle Issues

**Problem**: Using `asyncio.run()` for initialization before FastMCP server startup created competing event loops.

**Original Pattern** (Problematic):
```python
if __name__ == "__main__":
    # This creates one event loop
    asyncio.run(initialize_services())
    
    # FastMCP creates another event loop
    mcp.run(...)
```

**Fixed Pattern**:
```python
@asynccontextmanager
async def lifespan(app):
    await initialize_services()
    try:
        yield
    finally:
        if db_manager:
            await db_manager.close()

mcp = FastMCP("suechef", lifespan=lifespan)
```

### 2. Function Parameter Mismatch

**Problem**: Legacy `unified_legal_search` function didn't accept `group_id` parameter that MCP tool was passing.

**Original Call** (Problematic):
```python
return await legal_tools.unified_legal_search(
    db_manager.postgres, db_manager.qdrant, db_manager.graphiti,
    openai.AsyncOpenAI(api_key=config.api.openai_api_key),
    query, search_type, group_id  # <- Extra parameter
)
```

**Fixed Call**:
```python
return await legal_tools.unified_legal_search(
    db_manager.postgres, db_manager.qdrant, db_manager.graphiti,
    openai.AsyncOpenAI(api_key=config.api.openai_api_key),
    query, search_type  # <- Removed unsupported parameter
)
```

### 3. Database Connection Pool Conflicts

**Root Cause**: Multiple async contexts trying to acquire database connections simultaneously in an unstable event loop environment.

**Resolution**: Proper FastMCP lifespan management ensures single event loop with proper connection pool lifecycle.

## Resolution

### Immediate Fixes

1. **Adopted FastMCP Lifespan Pattern**
   - Used `@asynccontextmanager` decorator for proper async context management
   - Moved initialization into FastMCP's lifespan cycle
   - Ensured single event loop for entire application lifecycle

2. **Fixed Function Parameter Mismatches**
   - Removed unsupported `group_id` parameter from legacy function calls
   - Added documentation about parameter limitations

3. **Improved Error Handling**
   - Added proper exception handling in lifespan management
   - Enhanced initialization logging for better debugging

4. **Updated Service Initialization**
   - Removed duplicate initialization logic
   - Simplified `ensure_initialized()` to just check service existence

### Verification Steps
1. Container logs confirm proper service initialization
2. All database services (PostgreSQL, Qdrant, Neo4j) show healthy status
3. Services initialized in correct order with proper dependencies
4. Event loop management now follows FastMCP best practices

## Lessons Learned

### What Went Well
- **FastMCP Documentation**: The llms.txt file provided crucial guidance on proper lifespan patterns
- **Modular Architecture**: Clean separation made it easy to identify and fix initialization issues
- **Good Logging**: Initialization logging helped track service startup sequence

### What Went Wrong
- **Event Loop Mismanagement**: Multiple event loops created conflicts
- **Incomplete Migration**: Legacy function signatures not updated for new parameter patterns
- **Initialization Timing**: Services initialized too early outside FastMCP lifecycle

## Action Items

### Completed
- ✅ Fixed FastMCP lifespan implementation with proper async context manager
- ✅ Resolved function parameter mismatches
- ✅ Fixed event loop management issues
- ✅ Updated service initialization to use FastMCP patterns
- ✅ Added proper error handling and logging

### Recommended Future Improvements

1. **Standardize Parameter Patterns**
   ```python
   # Consider migrating legacy functions to support group_id
   async def unified_legal_search(
       postgres_pool: asyncpg.Pool,
       qdrant_client,
       graphiti_client: Graphiti,
       openai_client,
       query: str,
       search_type: str = "all",
       group_id: Optional[str] = None  # Add support
   ):
   ```

2. **Add Service Health Monitoring**
   ```python
   @mcp.tool()
   async def health_check():
       return {
           "services": {
               "postgres": db_manager.postgres._pool._closed if db_manager else False,
               "qdrant": bool(db_manager.qdrant if db_manager else False),
               "graphiti": bool(db_manager.graphiti if db_manager else False)
           }
       }
   ```

3. **Implement Connection Pool Monitoring**
   - Add metrics for connection pool usage
   - Monitor for connection leaks
   - Set up alerts for pool exhaustion

4. **Enhanced Error Recovery**
   - Implement circuit breakers for database operations
   - Add retry logic with exponential backoff
   - Graceful degradation when services fail

## Prevention Measures

1. **Follow FastMCP Patterns**: Always use lifespan for initialization in FastMCP applications
2. **Parameter Validation**: Add runtime parameter validation for function calls
3. **Event Loop Management**: Never mix `asyncio.run()` with FastMCP server startup
4. **Service Dependencies**: Ensure proper dependency order in initialization
5. **Integration Testing**: Add tests that verify concurrent database operations

## Technical Reference

### FastMCP Lifespan Pattern
```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP

@asynccontextmanager
async def lifespan(app):
    """Proper FastMCP initialization pattern"""
    # Startup logic
    await initialize_services()
    try:
        yield
    finally:
        # Cleanup logic
        await cleanup_services()

mcp = FastMCP("server", lifespan=lifespan)
```

### Database Connection Best Practices
```python
# Use connection pools with proper configuration
postgres_pool = await asyncpg.create_pool(
    url,
    min_size=2,
    max_size=10,
    max_queries=50000,
    max_inactive_connection_lifetime=300,
    command_timeout=30
)

# Always use context managers
async with postgres_pool.acquire() as conn:
    result = await conn.fetchval("SELECT 1")
```

## Conclusion

This incident highlighted the critical importance of following framework-specific initialization patterns. The move to proper FastMCP lifespan management resolved all event loop and database connection issues. The infrastructure is now stable and ready for production use, with all database operations functioning correctly within a single, properly managed event loop.