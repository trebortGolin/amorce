"""
MCP Client - Communicates with MCP servers using the Model Context Protocol

Supports:
- Tool discovery and call
- Resource listing and reading
- STDIO and SSE transport
"""

import asyncio
import json
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class MCPTool:
    """Represents an MCP tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPResource:
    """Represents an MCP resource."""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPClient:
    """
    Client for communicating with MCP servers.
    
    Supports STDIO transport (most common for MCP servers).
    """
    
    def __init__(self, command: List[str], server_name: str):
        """
        Initialize MCP client.
        
        Args:
            command: Command to start MCP server (e.g., ["npx", "server-name"])
            server_name: Friendly name for logging
        """
        self.command = command
        self.server_name = server_name
        self.process: Optional[subprocess.Popen] = None
        self._message_id = 0
        
    async def connect(self):
        """Start the MCP server process."""
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        
        # Send initialize request
        init_response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {}
            },
            "clientInfo": {
                "name": "amorce-mcp-bridge",
                "version": "0.1.0"
            }
        })
        
        # Send initialized notification
        await self._send_notification("notifications/initialized")
        
        return init_response
        
    async def disconnect(self):
        """Stop the MCP server process."""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            
    async def list_tools(self) -> List[MCPTool]:
        """
        Discover available tools from MCP server.
        
        Returns:
            List of available tools
        """
        response = await self._send_request("tools/list", {})
        tools = response.get("tools", [])
        
        return [
            MCPTool(
                name=tool["name"],
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {})
            )
            for tool in tools
        ]
        
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        return response.get("content", [])
        
    async def list_resources(self) -> List[MCPResource]:
        """
        Discover available resources from MCP server.
        
        Returns:
            List of available resources (empty if not supported)
        """
        try:
            response = await self._send_request("resources/list", {})
            resources = response.get("resources", [])
            
            return [
                MCPResource(
                    uri=res["uri"],
                    name=res["name"],
                    description=res.get("description"),
                    mime_type=res.get("mimeType")
                )
                for res in resources
            ]
        except Exception as e:
            # Some MCP servers don't support resources
            if "Method not found" in str(e):
                return []
            raise
        
    async def read_resource(self, uri: str) -> Any:
        """
        Read a resource from the MCP server.
        
        Args:
            uri: Resource URI
            
        Returns:
            Resource contents
        """
        response = await self._send_request("resources/read", {
            "uri": uri
        })
        
        return response.get("contents", [])
        
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send JSON-RPC request to MCP server.
        
        Args:
            method: RPC method name
            params: Method parameters
            
        Returns:
            Response data
        """
        self._message_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._message_id,
            "method": method,
            "params": params
        }
        
        # Write request
        request_str = json.dumps(message) + "\n"
        self.process.stdin.write(request_str)
        self.process.stdin.flush()
        
        # Read response
        response_str = self.process.stdout.readline()
        response = json.loads(response_str)
        
        if "error" in response:
            raise Exception(f"MCP Error: {response['error']}")
            
        return response.get("result", {})
        
    async def _send_notification(self, method: str, params: Dict[str, Any] = None):
        """
        Send JSON-RPC notification (no response expected).
        
        Args:
            method: Notification method name
            params: Notification parameters
        """
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        notification_str = json.dumps(message) + "\n"
        self.process.stdin.write(notification_str)
        self.process.stdin.flush()
        
    def __enter__(self):
        """Context manager entry."""
        asyncio.run(self.connect())
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        asyncio.run(self.disconnect())
