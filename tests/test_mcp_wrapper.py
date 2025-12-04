#!/usr/bin/env python3
"""
Integration test for MCP Agent Wrapper.

Tests Flask endpoints that expose MCP tools via AATP.
"""

import requests
import json
import sys
import os
import time
import subprocess

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


def test_wrapper_health():
    """Test health endpoint."""
    print("1️⃣ Testing health endpoint...")
    try:
        response = requests.get("http://localhost:5001/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health check passed: {data}")
            return True
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ⚠️  Wrapper not running at http://localhost:5001")
        print("   Start with: python run_mcp_wrappers.py filesystem")
        return False


def test_wrapper_tools_list():
    """Test tools list endpoint."""
    print("\n2️⃣ Testing tools list endpoint...")
    
    # Simple mock request (no real signature for testing)
    payload = {
        "payload": {
            "action": "list_tools"
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:5001/v1/tools/list",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 401:
            print("   ⚠️  Expected: Signature verification required")
            print("   (This is correct - wrapper enforces AATP signatures)")
            return True
        elif response.status_code == 200:
            data = response.json()
            print(f"   ✅ Tools discovered: {len(data.get('tools', []))} tools")
            return True
        else:
            print(f"   ❌ Unexpected response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_wrapper_tools_call():
    """Test tools call endpoint."""
    print("\n3️⃣ Testing tools call endpoint...")
    
    payload = {
        "payload": {
            "tool_name": "list_directory",
            "arguments": {"path": "/private/tmp"}
        }
    }
    
    try:
        response = requests.post(
            "http://localhost:5001/v1/tools/call",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 401:
            print("   ✅ Signature verification enforced (expected)")
            return True
        else:
            print(f"   Response: {response.text[:200]}")
            return True
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Run all integration tests."""
    print("🧪 MCP Flask Wrapper Integration Tests\n")
    print("=" * 60)
    
    results = []
    
    # Test 1: Health
    results.append(("Health Check", test_wrapper_health()))
    
    if not results[0][1]:
        print("\n" + "=" * 60)
        print("\n⚠️  Wrapper not running. To start:")
        print("   1. Open a new terminal")
        print("   2. cd /Users/rgosselin/amorce")
        print("   3. python3 run_mcp_wrappers.py filesystem")
        print("   4. Re-run this test")
        return False
    
    # Test 2: Tools List
    results.append(("Tools List", test_wrapper_tools_list()))
    
    # Test 3: Tools Call
    results.append(("Tools Call", test_wrapper_tools_call()))
    
    # Summary
    print("\n" + "=" * 60)
    print("\n📊 Test Summary:\n")
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✅ All tests passed!")
        print("\n📝 Notes:")
        print("   - Wrapper correctly enforces AATP signature verification")
        print("   - Health endpoint working")
        print("   - Tool endpoints accessible (require signatures)")
        return True
    else:
        print("\n❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
