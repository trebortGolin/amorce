#!/usr/bin/env python3
"""
Simple test to verify MCP client can communicate with MCP server.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from adapters.mcp.mcp_client import MCPClient


async def test_mcp_client():
    """Test MCP client with filesystem server."""
    print("🧪 Testing MCP Client...\n")
    
    # Initialize client
    client = MCPClient(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        server_name="filesystem"
    )
    
    try:
        # Connect
        print("1️⃣ Connecting to MCP server...")
        init_response = await client.connect()
        print(f"   ✅ Connected: {init_response.get('serverInfo', {}).get('name', 'Unknown')}")
        
        # List tools
        print("\n2️⃣ Listing available tools...")
        tools = await client.list_tools()
        print(f"   ✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"      - {tool.name}: {tool.description}")
        
        # List resources
        print("\n3️⃣ Listing available resources...")
        resources = await client.list_resources()
        print(f"   ✅ Found {len(resources)} resources")
        
        # Test a simple tool call (list directory)
        if any(t.name == "list_directory" for t in tools):
            print("\n4️⃣ Testing tool: list_directory...")
            result = await client.call_tool("list_directory", {"path": "/tmp"})
            print(f"   ✅ Tool executed successfully")
            print(f"   Result (first 200 chars): {str(result)[:200]}...")
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Disconnect
        await client.disconnect()
        print("\n🔌 Disconnected")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_mcp_client())
    sys.exit(0 if success else 1)
