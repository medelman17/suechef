#!/usr/bin/env python3
"""
Debug script to inspect CourtListener API responses and understand the data structure.
"""

import asyncio
import aiohttp
import json
import os

async def debug_courtlistener_api():
    """Debug the CourtListener API response structure."""
    
    print("🔍 Debugging CourtListener API Response Structure")
    print("=" * 60)
    
    # Test with testCourtListenerConnection first
    print("1️⃣ Testing CourtListener connection...")
    
    connection_payload = {
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
            json=connection_payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            connection_content = json.loads(result.get("result", {}).get("content", "{}"))
            print(f"Connection Status: {connection_content.get('status', 'unknown')}")
            print()
    
    # Try importing a few different opinion IDs to see the response structure
    test_ids = [2295617, 1234567, 7654321]  # Mix of potentially valid and invalid IDs
    
    for opinion_id in test_ids:
        print(f"2️⃣ Testing importCourtOpinion with ID {opinion_id}...")
        
        import_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "importCourtOpinion",
                "arguments": {
                    "opinion_id": opinion_id,
                    "add_as_snippet": False,  # Don't create snippets for debugging
                    "auto_link_events": False,
                    "group_id": "debug_test"
                }
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://localhost:8000/mcp/",
                json=import_payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                import_result = await response.json()
                
                if import_result.get("result", {}).get("isError"):
                    print(f"❌ Import failed for ID {opinion_id}")
                    error_content = import_result.get("result", {}).get("content", "")
                    print(f"   Error: {error_content}")
                else:
                    try:
                        import_content = json.loads(import_result.get("result", {}).get("content", "{}"))
                        debug_info = import_content.get("debug_info", {})
                        
                        print(f"✅ Import succeeded for ID {opinion_id}")
                        print(f"   API Endpoint Used: {debug_info.get('api_endpoint_used', 'N/A')}")
                        print(f"   Has Error: {debug_info.get('has_error', 'N/A')}")
                        print(f"   Response Keys: {debug_info.get('cluster_response_keys', [])}")
                        print(f"   Extracted Case Name: '{debug_info.get('extracted_case_name', 'N/A')}'")
                        print(f"   Extracted Court: '{debug_info.get('extracted_court', 'N/A')}'")
                        print(f"   Opinion Text Length: {debug_info.get('opinion_text_length', 0)}")
                        print(f"   Fallback Used: {debug_info.get('fallback_used', False)}")
                        
                        # Show some of the actual API response structure for debugging
                        response_keys = debug_info.get('cluster_response_keys', [])
                        if response_keys:
                            print(f"   Available Fields in API Response: {response_keys}")
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error for ID {opinion_id}: {e}")
                
                print()
    
    # Try a direct search to see what IDs are actually available
    print("3️⃣ Searching for real case IDs...")
    
    search_payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "searchCourtOpinions",
            "arguments": {
                "query": "landlord tenant water damage",
                "limit": 3
            }
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/mcp/",
            json=search_payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            search_result = await response.json()
            
            if not search_result.get("result", {}).get("isError"):
                search_content = json.loads(search_result.get("result", {}).get("content", "{}"))
                results = search_content.get("results", [])
                
                if results:
                    print(f"✅ Found {len(results)} search results")
                    for i, result in enumerate(results[:2]):  # Test first 2 results
                        opinion_id = result.get("id")
                        print(f"   Result {i+1}: ID {opinion_id}, Case: {result.get('case_name', 'N/A')}")
                        
                        # Test importing this actual result
                        if opinion_id:
                            print(f"      Testing import of ID {opinion_id}...")
                            
                            test_import_payload = {
                                "jsonrpc": "2.0",
                                "id": 4,
                                "method": "tools/call",
                                "params": {
                                    "name": "importCourtOpinion",
                                    "arguments": {
                                        "opinion_id": opinion_id,
                                        "add_as_snippet": False,
                                        "auto_link_events": False,
                                        "group_id": "debug_test"
                                    }
                                }
                            }
                            
                            async with aiohttp.ClientSession() as session2:
                                async with session2.post(
                                    "http://localhost:8000/mcp/",
                                    json=test_import_payload,
                                    headers={"Content-Type": "application/json"}
                                ) as response2:
                                    test_result = await response2.json()
                                    
                                    if not test_result.get("result", {}).get("isError"):
                                        test_content = json.loads(test_result.get("result", {}).get("content", "{}"))
                                        debug_info = test_content.get("debug_info", {})
                                        
                                        print(f"      ✅ Case Name: '{debug_info.get('extracted_case_name', 'N/A')}'")
                                        print(f"      📄 Text Length: {debug_info.get('opinion_text_length', 0)}")
                                        print(f"      🔗 API Keys: {debug_info.get('cluster_response_keys', [])[:5]}...")
                                    else:
                                        print(f"      ❌ Import failed")
                else:
                    print("⚠️  No search results found")
            else:
                print("❌ Search failed")

if __name__ == "__main__":
    asyncio.run(debug_courtlistener_api())