#!/usr/bin/env python3
"""Test getSystemStatus tool to verify fix."""

import asyncio
import aiohttp
import json

async def test_system_status():
    payload = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'tools/call',
        'params': {
            'name': 'getSystemStatus',
            'arguments': {}
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'http://localhost:8000/mcp/',
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            }
        ) as response:
            result = await response.json()
            if 'result' in result and not result.get('result', {}).get('isError'):
                content = json.loads(result['result']['content'])
                print('✅ getSystemStatus succeeded!')
                print('System Status:', content.get('status', 'unknown'))
                print('Message:', content.get('message', 'no message'))
                return True
            else:
                print('❌ getSystemStatus failed!')
                if 'result' in result:
                    print('Error:', result['result'].get('content', result))
                else:
                    print('Error:', result)
                return False

if __name__ == "__main__":
    success = asyncio.run(test_system_status())
    print("Test result:", "PASSED" if success else "FAILED")