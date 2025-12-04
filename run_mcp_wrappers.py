#!/usr/bin/env python3
"""
MCP Wrapper Launcher

Starts MCP agent wrappers based on configuration.
Usage:
  python run_mcp_wrappers.py                    # Start all enabled servers
  python run_mcp_wrappers.py filesystem         # Start specific server
  python run_mcp_wrappers.py --list             # List available servers
"""

import argparse
import json
import sys
import os
from adapters.mcp.mcp_agent_wrapper import MCPAgentWrapper


def load_mcp_config():
    """Load MCP server configuration."""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'mcp_servers.json')
    with open(config_path, 'r') as f:
        return json.load(f)


def list_servers(config):
    """List available MCP servers."""
    print("\n📋 Available MCP Servers:\n")
    for server in config['mcp_servers']:
        status = "✅ enabled" if server.get('enabled') else "❌ disabled"
        print(f"  {server['name']} - {status}")
        print(f"    Agent ID: {server['agent_id']}")
        print(f"    Port: {server['port']}")
        print(f"    Description: {server.get('description', 'N/A')}")
        if server.get('require_hitl_for'):
            print(f"    HITL Required: {', '.join(server['require_hitl_for'])}")
        print()


def start_server(server_config):
    """Start an MCP wrapper for a server."""
    name = server_config['name']
    command = server_config['command']
    port = server_config['port']
    require_hitl = server_config.get('require_hitl_for', [])
    
    print(f"\n🚀 Starting MCP wrapper for: {name}")
    print(f"   Command: {' '.join(command)}")
    print(f"   Port: {port}")
    print(f"   HITL Tools: {require_hitl or 'None'}\n")
    
    wrapper = MCPAgentWrapper(
        mcp_command=command,
        server_name=name,
        require_hitl_for=require_hitl,
        port=port
    )
    
    wrapper.run()


def main():
    parser = argparse.ArgumentParser(description='MCP Wrapper Launcher')
    parser.add_argument('server', nargs='?', help='Server name to start')
    parser.add_argument('--list', action='store_true', help='List available servers')
    
    args = parser.parse_args()
    
    config = load_mcp_config()
    
    if args.list:
        list_servers(config)
        return
    
    if args.server:
        # Start specific server
        server = next((s for s in config['mcp_servers'] if s['name'] == args.server), None)
        if not server:
            print(f"❌ Server '{args.server}' not found")
            print("\nAvailable servers:")
            list_servers(config)
            sys.exit(1)
        
        start_server(server)
    else:
        # Start all enabled servers (simplified - just start first enabled)
        enabled_servers = [s for s in config['mcp_servers'] if s.get('enabled')]
        
        if not enabled_servers:
            print("❌ No enabled servers found")
            print("\nTo enable a server, edit config/mcp_servers.json and set 'enabled': true")
            print("\nAvailable servers:")
            list_servers(config)
            sys.exit(1)
        
        print(f"\n📦 Starting {len(enabled_servers)} enabled MCP server(s)...\n")
        
        # For simplicity, start first enabled server
        # In production, would use multiprocessing for multiple servers
        start_server(enabled_servers[0])


if __name__ == "__main__":
    main()
