#!/usr/bin/env python3
"""
CourtListener Integration Test Script

This script tests the fixed CourtListener integration to verify
that the 400 Bad Request errors have been resolved.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import courtlistener_tools

async def test_api_key_configuration():
    """Test if API key is properly configured."""
    print("🔧 Testing API Key Configuration...")
    
    api_key = os.getenv("COURTLISTENER_API_KEY")
    if not api_key:
        print("❌ COURTLISTENER_API_KEY not found in environment")
        print("📋 Fix: Add COURTLISTENER_API_KEY=your_key to .env file")
        return False
    
    print(f"✅ API key found (length: {len(api_key)})")
    return True

async def test_connection():
    """Test basic connection to CourtListener."""
    print("\n🌐 Testing CourtListener Connection...")
    
    result = await courtlistener_tools.test_courtlistener_connection()
    
    if result.get("status") == "success":
        print("✅ Connection successful!")
        print(f"   Test search returned {result.get('test_search_count', 0)} results")
        return True
    else:
        print("❌ Connection failed:")
        print(f"   Error: {result.get('message')}")
        if result.get("fix"):
            print(f"   Fix: {result.get('fix')}")
        return False

async def test_search_functions():
    """Test the previously failing search functions."""
    print("\n🔍 Testing Search Functions...")
    
    tests = [
        ("Opinion Search", lambda: courtlistener_tools.search_courtlistener_opinions("construction", limit=2)),
        ("Docket Search", lambda: courtlistener_tools.search_courtlistener_dockets(case_name="Smith", limit=2)),
        ("Citation Search", lambda: courtlistener_tools.find_citing_opinions("Brown v. Board", limit=2)),
    ]
    
    results = {}
    for test_name, test_func in tests:
        print(f"  Testing {test_name}...")
        try:
            result = await test_func()
            if result.get("status") == "success":
                count = result.get("count", 0)
                print(f"  ✅ {test_name}: Found {count} results")
                results[test_name] = True
            else:
                print(f"  ❌ {test_name}: {result.get('message', 'Unknown error')}")
                results[test_name] = False
        except Exception as e:
            print(f"  ❌ {test_name}: Exception - {str(e)}")
            results[test_name] = False
    
    return all(results.values())

async def test_analysis_function():
    """Test the analyze_courtlistener_precedents function that was failing with None errors."""
    print("\n📊 Testing Analysis Function...")
    
    try:
        result = await courtlistener_tools.analyze_courtlistener_precedents(
            topic="municipal law", 
            date_range_years=10, 
            min_citations=5
        )
        
        if result.get("status") == "success":
            analysis = result.get("analysis", {})
            case_count = analysis.get("total_relevant_cases", 0)
            print(f"✅ Analysis successful: Found {case_count} relevant cases")
            print(f"   Time period: {analysis.get('time_period')}")
            return True
        else:
            print(f"❌ Analysis failed: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Analysis exception: {str(e)}")
        return False

async def main():
    """Run all diagnostic tests."""
    print("🍳 SueChef CourtListener Integration Test")
    print("=" * 50)
    
    tests = [
        ("API Key Configuration", test_api_key_configuration),
        ("Basic Connection", test_connection),
        ("Search Functions", test_search_functions),
        ("Analysis Function", test_analysis_function),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results[test_name] = False
    
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All tests passed! CourtListener integration is working.")
        print("   The 400 Bad Request errors have been fixed.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above for details.")
        print("   Common fixes:")
        print("   - Set COURTLISTENER_API_KEY in .env file")
        print("   - Restart Docker: docker-compose restart suechef")
        print("   - Check internet connection")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main()) 