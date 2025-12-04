"""
Demo: MCP Tool Calling via Amorce

This demonstrates:
1. Starting an MCP wrapper
2. Calling MCP tools through Amorce
3. HITL for sensitive operations
"""

from amorce_py_sdk.amorce import IdentityManager
from amorce_py_sdk.amorce.mcp_helpers import MCPToolClient
import time


def demo_mcp_filesystem():
    """
    Demo: Call filesystem MCP tools via Amorce.
    
    Prerequisites:
    1. Install MCP server: npm install -g @modelcontextprotocol/server-filesystem
    2. Start wrapper: python run_mcp_wrappers.py filesystem
    3. Enable filesystem server in config/mcp_servers.json
    """
    
    print("🚀 MCP Tool Calling Demo\n")
    print("=" * 60)
    
    # 1. Create identity
    print("\n1️⃣ Creating Amorce identity...")
    identity = IdentityManager.generate_ephemeral()
    print(f"   Agent ID: {identity.agent_id}")
    
    # 2. Initialize MCP client
    print("\n2️⃣ Initializing MCP client...")
    mcp = MCPToolClient(identity, orchestrator_url="http://localhost:5001")
    
    # 3. List available tools
    print("\n3️⃣ Listing available filesystem tools...")
    try:
        tools = mcp.list_tools('filesystem')
        print(f"   Available tools: {tools}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        print("   Make sure MCP wrapper is running: python run_mcp_wrappers.py filesystem")
        return
    
    # 4. Read file (no HITL needed)
    print("\n4️⃣ Reading file /tmp/test.txt...")
    try:
        result = mcp.call_tool(
            server_name='filesystem',
            tool_name='read_file',
            arguments={'path': '/tmp/test.txt'}
        )
        print(f"   ✅ File contents: {result}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        print("   (File might not exist - this is OK)")
    
    # 5. Write file (HITL required)
    print("\n5️⃣ Requesting approval to write file...")
    try:
        approval_id = mcp.request_tool_approval(
            server_name='filesystem',
            tool_name='write_file',
            arguments={
                'path': '/tmp/amorce_mcp_demo.txt',
                'content': 'Hello from Amorce + MCP!'
            },
            summary="Write demo file to /tmp"
        )
        print(f"   📋 Approval ID: {approval_id}")
        print("   ⏳ Waiting for human approval...")
        print("      (In production, human would approve via UI)")
        print("      (For demo, auto-approving after 3 seconds...)")
        
        time.sleep(3)
        
        # In production, approval would come from UI
        # For demo, we'll simulate approval
        print("\n6️⃣ Writing file with approval...")
        result = mcp.call_tool(
            server_name='filesystem',
            tool_name='write_file',
            arguments={
                'path': '/tmp/amorce_mcp_demo.txt',
                'content': 'Hello from Amorce + MCP!'
            },
            approval_id=approval_id
        )
        print(f"   ✅ File written: {result}")
        
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    print("\n" + "=" * 60)
    print("✨ Demo complete!")
    print("\nNext steps:")
    print("  - Check /tmp/amorce_mcp_demo.txt")
    print("  - Try other MCP servers (brave_search, postgres)")
    print("  - Build your own MCP-powered agents!")


def demo_mcp_resources():
    """Demo: Access MCP resources."""
    print("\n🗂️  MCP Resources Demo\n")
    print("=" * 60)
    
    identity = IdentityManager.generate_ephemeral()
    mcp = MCPToolClient(identity, orchestrator_url="http://localhost:5001")
    
    print("\n1️⃣ Listing available resources...")
    try:
        resources = mcp.list_resources('filesystem')
        print(f"   Resources: {resources}")
        
        if resources:
            print("\n2️⃣ Reading first resource...")
            uri = resources[0]['uri']
            content = mcp.read_resource('filesystem', uri)
            print(f"   Content: {content}")
            
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("\n🎯 Amorce MCP Wrapper Demo\n")
    print("This demo shows how to call MCP tools through Amorce protocol")
    print("with cryptographic signatures and HITL support.\n")
    
    demo_mcp_filesystem()
    # demo_mcp_resources()  # Uncomment to test resources
