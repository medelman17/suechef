#!/usr/bin/env python3
"""Simple test to check CourtListener connection status."""

import asyncio
import aiohttp
import json

async def test_connection():
    """Test CourtListener connection."""
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "testCourtListenerConnection",
            "arguments": {}
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/mcp/",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            content = json.loads(result.get("result", {}).get("content", "{}"))
            
            print("CourtListener Connection Test Result:")
            print(json.dumps(content, indent=2))

if __name__ == "__main__":
    asyncio.run(test_connection())