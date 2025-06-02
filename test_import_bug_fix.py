#!/usr/bin/env python3
"""
Test script to validate importCourtOpinion bug fixes.

This script tests the specific bug reported where importCourtOpinion
was returning "Unknown Case" and placeholder data instead of extracting
actual case information from CourtListener.
"""

import asyncio
import aiohttp
import json
import os

async def test_import_court_opinion():
    """Test the importCourtOpinion function with the reported bug case."""
    
    # Test the specific case mentioned in the bug report
    test_opinion_id = 2295617  # Ocean Park Associates v. Santa Monica Rent Control Board
    
    print("🧪 Testing importCourtOpinion Bug Fix")
    print("=" * 50)
    print(f"Testing Opinion ID: {test_opinion_id}")
    print("Expected: Ocean Park Associates v. Santa Monica Rent Control Board")
    print()
    
    # First test the search to confirm the case exists
    print("1️⃣ Testing searchCourtOpinions to confirm case data exists...")
    
    search_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "searchCourtOpinions",
            "arguments": {
                "query": "Ocean Park Associates Santa Monica Rent Control",
                "limit": 5
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
            
            if search_result.get("result", {}).get("isError"):
                print("❌ Search failed:", search_result.get("result", {}).get("content"))
                return
            
            search_content = json.loads(search_result.get("result", {}).get("content", "{}"))
            print(f"✅ Search found {search_content.get('count', 0)} results")
            
            # Check if our test case is in the results
            found_test_case = False
            for result in search_content.get("results", []):
                if result.get("id") == test_opinion_id:
                    found_test_case = True
                    print(f"✅ Found test case in search results:")
                    print(f"   Case Name: {result.get('case_name', 'N/A')}")
                    print(f"   Court: {result.get('court', 'N/A')}")
                    print(f"   Date: {result.get('date_filed', 'N/A')}")
                    break
            
            if not found_test_case:
                print(f"⚠️  Test case ID {test_opinion_id} not found in search results")
                print("   This might be expected - continuing with import test...")
    
    print()
    print("2️⃣ Testing importCourtOpinion with the bug fix...")
    
    # Test the import function
    import_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "importCourtOpinion",
            "arguments": {
                "opinion_id": test_opinion_id,
                "add_as_snippet": True,
                "auto_link_events": True,
                "group_id": "test_bug_fix"
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
                print("❌ Import failed:", import_result.get("result", {}).get("content"))
                return
            
            import_content = json.loads(import_result.get("result", {}).get("content", "{}"))
            
            # Analyze the results
            print("🔍 Import Results Analysis:")
            print("-" * 30)
            
            import_summary = import_content.get("import_summary", {})
            extracted_concepts = import_content.get("extracted_concepts", {})
            debug_info = import_content.get("debug_info")
            
            # Check if bug is fixed
            case_name = import_summary.get("case_name", "")
            court = import_summary.get("court", "")
            date_filed = import_summary.get("date_filed")
            
            print(f"📋 Case Name: {case_name}")
            print(f"🏛️  Court: {court}")
            print(f"📅 Date Filed: {date_filed}")
            print(f"⚖️  Jurisdiction: {import_summary.get('jurisdiction', 'N/A')}")
            print(f"🎯 Importance: {import_summary.get('estimated_importance', 'N/A')}")
            print()
            
            # Bug status assessment
            bug_fixed = True
            issues = []
            
            if case_name == "Unknown Case":
                bug_fixed = False
                issues.append("❌ Case name still shows 'Unknown Case'")
            else:
                print("✅ Case name extracted successfully")
            
            if court == "Unknown Court":
                bug_fixed = False  
                issues.append("❌ Court still shows 'Unknown Court'")
            else:
                print("✅ Court information extracted successfully")
                
            if not date_filed:
                issues.append("⚠️  Date filed is null")
            else:
                print("✅ Date filed extracted successfully")
            
            # Check extracted concepts
            holdings = extracted_concepts.get("holdings", [])
            practice_areas = extracted_concepts.get("practice_areas", [])
            parties = extracted_concepts.get("parties", [])
            
            print(f"📚 Legal Holdings: {len(holdings)} found")
            print(f"🏢 Practice Areas: {len(practice_areas)} found - {practice_areas}")
            print(f"👥 Parties: {len(parties)} found - {parties}")
            
            if len(holdings) == 0 and len(practice_areas) == 0:
                issues.append("⚠️  No legal concepts extracted")
            
            # Debug information
            if debug_info:
                print()
                print("🐛 Debug Information:")
                print(f"   API Endpoint: {debug_info.get('api_endpoint_used', 'N/A')}")
                print(f"   Text Length: {debug_info.get('opinion_text_length', 0)} characters")
                print(f"   Citations Found: {debug_info.get('citations_found', 0)}")
                print(f"   Has Sub-opinions: {debug_info.get('has_sub_opinions', False)}")
            
            print()
            print("🎯 FINAL ASSESSMENT:")
            print("=" * 20)
            
            if bug_fixed and len(issues) <= 1:  # Allow for minor issues like missing date
                print("✅ BUG FIXED! importCourtOpinion now extracts meaningful case information")
            elif len(issues) <= 2:
                print("🔄 PARTIALLY FIXED - Significant improvement but some issues remain:")
                for issue in issues:
                    print(f"   {issue}")
            else:
                print("❌ BUG STILL EXISTS - Multiple extraction failures:")
                for issue in issues:
                    print(f"   {issue}")
            
            print()
            print("💾 Test completed - imported case saved with group_id: 'test_bug_fix'")

if __name__ == "__main__":
    print("Starting CourtListener Import Bug Fix Test...")
    print()
    asyncio.run(test_import_court_opinion())