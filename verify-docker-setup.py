#!/usr/bin/env python3
"""
SueChef Docker Setup Verification Script
This script verifies that all Docker services are running and accessible.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any

# Check if we can import required modules (optional for this verification)
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False


async def verify_services() -> Dict[str, Any]:
    """Verify all SueChef services are accessible."""
    results = {
        "postgresql": {"status": "unknown", "details": ""},
        "qdrant": {"status": "unknown", "details": ""},
        "neo4j": {"status": "unknown", "details": ""},
        "suechef_mcp": {"status": "unknown", "details": ""},
        "summary": {"total": 4, "healthy": 0, "issues": []}
    }
    
    # Test Qdrant
    if AIOHTTP_AVAILABLE:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:6333/") as resp:
                    if resp.status == 200:
                        qdrant_info = await resp.json()
                        version = qdrant_info.get('version', 'unknown')
                        results["qdrant"]["status"] = "healthy"
                        results["qdrant"]["details"] = f"Qdrant {version} is running"
                        results["summary"]["healthy"] += 1
                    else:
                        results["qdrant"]["status"] = "unhealthy"
                        results["qdrant"]["details"] = f"HTTP {resp.status}"
                        results["summary"]["issues"].append("Qdrant not responding properly")
        except Exception as e:
            results["qdrant"]["status"] = "error"
            results["qdrant"]["details"] = str(e)
            results["summary"]["issues"].append(f"Qdrant connection error: {e}")
    else:
        results["qdrant"]["status"] = "skipped"
        results["qdrant"]["details"] = "aiohttp not available for testing"
    
    # Test PostgreSQL
    if ASYNCPG_AVAILABLE:
        try:
            conn = await asyncpg.connect(
                "postgresql://postgres:suechef_password@localhost:5432/legal_research"
            )
            result = await conn.fetchval("SELECT 'PostgreSQL is ready!' as status")
            await conn.close()
            results["postgresql"]["status"] = "healthy"
            results["postgresql"]["details"] = result
            results["summary"]["healthy"] += 1
        except Exception as e:
            results["postgresql"]["status"] = "error"
            results["postgresql"]["details"] = str(e)
            results["summary"]["issues"].append(f"PostgreSQL connection error: {e}")
    else:
        results["postgresql"]["status"] = "skipped"
        results["postgresql"]["details"] = "asyncpg not available for testing"
    
    # Test Neo4j
    if NEO4J_AVAILABLE:
        try:
            driver = GraphDatabase.driver(
                "bolt://localhost:7687", 
                auth=("neo4j", "suechef_neo4j_password")
            )
            with driver.session() as session:
                result = session.run("RETURN 'Neo4j is ready!' as status")
                status = result.single()["status"]
                results["neo4j"]["status"] = "healthy"
                results["neo4j"]["details"] = status
                results["summary"]["healthy"] += 1
            driver.close()
        except Exception as e:
            results["neo4j"]["status"] = "error"
            results["neo4j"]["details"] = str(e)
            results["summary"]["issues"].append(f"Neo4j connection error: {e}")
    else:
        results["neo4j"]["status"] = "skipped"
        results["neo4j"]["details"] = "neo4j driver not available for testing"
    
    # Test SueChef MCP Streaming HTTP
    if AIOHTTP_AVAILABLE:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8000/mcp") as resp:
                    if resp.status == 200:
                        results["suechef_mcp"]["status"] = "healthy"
                        results["suechef_mcp"]["details"] = "SueChef MCP Streaming HTTP endpoint is responding"
                        results["summary"]["healthy"] += 1
                    else:
                        results["suechef_mcp"]["status"] = "unhealthy"
                        results["suechef_mcp"]["details"] = f"HTTP {resp.status}"
                        results["summary"]["issues"].append("SueChef MCP endpoint not responding properly")
        except Exception as e:
            results["suechef_mcp"]["status"] = "error"
            results["suechef_mcp"]["details"] = str(e)
            results["summary"]["issues"].append(f"SueChef MCP connection error: {e}")
    else:
        results["suechef_mcp"]["status"] = "skipped"
        results["suechef_mcp"]["details"] = "aiohttp not available for testing"
    
    return results


def print_results(results: Dict[str, Any]):
    """Print verification results in a readable format."""
    print("🍳 SueChef Docker Setup Verification")
    print("=" * 50)
    
    # Service status
    for service, info in results.items():
        if service == "summary":
            continue
            
        status = info["status"]
        details = info["details"]
        
        if status == "healthy":
            icon = "✅"
        elif status == "skipped":
            icon = "⏭️"
        else:
            icon = "❌"
        
        print(f"{icon} {service.upper()}: {status}")
        print(f"   {details}")
        print()
    
    # Summary
    summary = results["summary"]
    print("📊 SUMMARY")
    print(f"   Services tested: {summary['total']}")
    print(f"   Healthy: {summary['healthy']}")
    print(f"   Issues: {len(summary['issues'])}")
    
    if summary["issues"]:
        print("\n⚠️  ISSUES FOUND:")
        for issue in summary["issues"]:
            print(f"   • {issue}")
    
    if summary["healthy"] == summary["total"]:
        print("\n🎉 All services are healthy! SueChef is ready to cook up some legal strategies!")
        return True
    else:
        print(f"\n🔧 {summary['total'] - summary['healthy']} service(s) need attention.")
        return False


async def main():
    """Main verification function."""
    print("Starting SueChef Docker setup verification...")
    print()
    
    # Check if modules are available
    missing_modules = []
    if not ASYNCPG_AVAILABLE:
        missing_modules.append("asyncpg")
    if not AIOHTTP_AVAILABLE:
        missing_modules.append("aiohttp")
    if not NEO4J_AVAILABLE:
        missing_modules.append("neo4j")
    
    if missing_modules:
        print("⚠️  Some Python modules are not available for testing:")
        for module in missing_modules:
            print(f"   • {module}")
        print("   Run 'uv sync' to install all dependencies for full testing.")
        print()
    
    results = await verify_services()
    success = print_results(results)
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nVerification cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)