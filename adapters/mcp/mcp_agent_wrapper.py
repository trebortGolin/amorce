"""
MCP Agent Wrapper - Exposes MCP server as an Amorce agent

Handles:
- AATP request verification
- Translation of AATP requests to MCP protocol
- Tool discovery and execution
- HITL (Human-in-the-Loop) for specific tools
- Response formatting
"""

import asyncio
import logging
import requests
import subprocess
from flask import Flask, request, jsonify
from typing import List, Dict, Any, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Production imports - NO FALLBACK
from amorce_py_sdk.amorce.verification import verify_request
from amorce_py_sdk.amorce.exceptions import AmorceSecurityError

from .mcp_client import MCPClient, MCPTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MCPAgentWrapper:
    """
    Wraps an MCP server as an Amorce agent.
    
    Provides AATP endpoints that translate to MCP protocol calls.
    """
    
    def __init__(
        self,
        mcp_command: List[str],
        server_name: str,
        require_hitl_for: Optional[List[str]] = None,
        port: int = 5000,
        orchestrator_url: Optional[str] = None,
        trust_directory_url: Optional[str] = None
    ):
        """
        Initialize MCP agent wrapper.
        
        Args:
            mcp_command: Command to start MCP server
            server_name: Server name for logging
            require_hitl_for: List of tool names requiring HITL approval
            port: Port to run Flask app on
        """
        self.mcp_client = MCPClient(mcp_command, server_name)
        self.server_name = server_name
        self.require_hitl = require_hitl_for or []
        self.port = port
        self.orchestrator_url = orchestrator_url or os.getenv('ORCHESTRATOR_URL', 'http://localhost:8080')
        self.trust_directory_url = trust_directory_url or os.getenv('TRUST_DIRECTORY_URL')
        self.app = Flask(__name__)
        self.tools_cache: Optional[List[MCPTool]] = None
        
        logger.info(f"Initializing MCP wrapper for {server_name}")
        logger.info(f"Orchestrator: {self.orchestrator_url}")
        logger.info(f"HITL required for: {self.require_hitl}")
        
        self._setup_routes()
        
    def _setup_routes(self):
        """Set up Flask routes for AATP endpoints."""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint."""
            return jsonify({
                "status": "healthy",
                "server": self.server_name,
                "type": "mcp-wrapper"
            })
            
        @self.app.route('/v1/tools/list', methods=['POST'])
        def list_tools():
            """
            List available MCP tools as Amorce services.
            
            AATP endpoint for tool discovery.
            """
            try:
                # Verify AATP signature
                verified = verify_request(
                    headers=request.headers,
                    body=request.get_data()
                )
                
                # Get tools from MCP server
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                if not self.tools_cache:
                    tools = loop.run_until_complete(self._get_tools())
                    self.tools_cache = tools
                else:
                    tools = self.tools_cache
                
                # Format as AATP response
                return jsonify({
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.input_schema,
                            "requires_approval": tool.name in self.require_hitl
                        }
                        for tool in tools
                    ]
                })
                
            except AmorceSecurityError as e:
                return jsonify({"error": f"Unauthorized: {str(e)}"}), 401
            except Exception as e:
                return jsonify({"error": f"Internal error: {str(e)}"}), 500
                
        @self.app.route('/v1/tools/call', methods=['POST'])
        def call_tool():
            """
            Execute MCP tool via AATP.
            
            Expected payload:
            {
                "tool_name": "tool_name",
                "arguments": {...},
                "approval_id": "optional_approval_id"
            }
            """
            try:
                # Verify AATP signature
                verified = verify_request(
                    headers=request.headers,
                    body=request.get_data()
                )
                
                payload = verified.payload.get('payload', {})
                tool_name = payload.get('tool_name')
                arguments = payload.get('arguments', {})
                approval_id = payload.get('approval_id')
                agent_id = verified.agent_id
                
                if not tool_name:
                    logger.warning("Tool call missing tool_name")
                    return jsonify({"error": "Missing tool_name"}), 400
                
                logger.info(f"Tool call request: {tool_name} from agent {agent_id}")
                
                # HITL Check with orchestrator integration
                if tool_name in self.require_hitl:
                    if not approval_id:
                        # Tool requires approval but none provided
                        logger.info(f"HITL required for {tool_name}, no approval provided")
                        return jsonify({
                            "error": "Approval required",
                            "requires_hitl": True,
                            "tool_name": tool_name,
                            "message": f"Tool '{tool_name}' requires human approval before execution"
                        }), 403
                    
                    # Verify approval with orchestrator
                    approval_valid = self._verify_approval(approval_id, tool_name, agent_id)
                    if not approval_valid:
                        logger.warning(f"Invalid approval {approval_id} for tool {tool_name}")
                        return jsonify({
                            "error": "Invalid or expired approval",
                            "approval_id": approval_id
                        }), 403
                    
                    logger.info(f"Approval {approval_id} verified for {tool_name}")
                
                # Execute tool via MCP
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    result = loop.run_until_complete(
                        self._call_tool(tool_name, arguments)
                    )
                    
                    logger.info(f"Tool {tool_name} executed successfully")
                    
                    return jsonify({
                        "status": "success",
                        "tool_name": tool_name,
                        "result": result
                    })
                
                except subprocess.TimeoutExpired:
                    logger.error(f"MCP server timeout for tool {tool_name}")
                    return jsonify({"error": "MCP server timeout"}), 504
                except ConnectionError as e:
                    logger.error(f"MCP server connection error: {e}")
                    return jsonify({"error": "MCP server unavailable"}), 503
                except Exception as e:
                    logger.error(f"Tool execution failed for {tool_name}: {e}", exc_info=True)
                    return jsonify({"error": f"Tool execution failed: {str(e)}"}), 500
                
            except AmorceSecurityError as e:
                return jsonify({"error": f"Unauthorized: {str(e)}"}), 401
            except Exception as e:
                return jsonify({"error": f"Tool execution failed: {str(e)}"}), 500
                
        @self.app.route('/v1/resources/list', methods=['POST'])
        def list_resources():
            """List available MCP resources."""
            try:
                verified = verify_request(
                    headers=request.headers,
                    body=request.get_data()
                )
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                resources = loop.run_until_complete(
                    self.mcp_client.list_resources()
                )
                
                return jsonify({
                    "resources": [
                        {
                            "uri": res.uri,
                            "name": res.name,
                            "description": res.description,
                            "mime_type": res.mime_type
                        }
                        for res in resources
                    ]
                })
                
            except AmorceSecurityError as e:
                return jsonify({"error": f"Unauthorized: {str(e)}"}), 401
            except Exception as e:
                return jsonify({"error": str(e)}), 500
                
        @self.app.route('/v1/resources/read', methods=['POST'])
        def read_resource():
            """Read an MCP resource."""
            try:
                verified = verify_request(
                    headers=request.headers,
                    body=request.get_data()
                )
                
                payload = verified.payload.get('payload', {})
                uri = payload.get('uri')
             
                if not uri:
                    return jsonify({"error": "Missing uri"}), 400
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                contents = loop.run_until_complete(
                    self.mcp_client.read_resource(uri)
                )
                
                return jsonify({
                    "uri": uri,
                    "contents": contents
                })
                
            except AmorceSecurityError as e:
                return jsonify({"error": f"Unauthorized: {str(e)}"}), 401
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    
    def _verify_approval(self, approval_id: str, tool_name: str, agent_id: str) -> bool:
        """
        Verify approval with orchestrator HITL API.
        
        Args:
            approval_id: Approval ID to verify
            tool_name: Tool being called
            agent_id: Agent requesting the tool call
            
        Returns:
            True if approval is valid and approved, False otherwise
        """
        try:
            response = requests.get(
                f"{self.orchestrator_url}/v1/approvals/{approval_id}",
                timeout=5
            )
            
            if response.status_code == 200:
                approval_data = response.json()
                # Verify approval matches the request
                if (approval_data.get('status') == 'approved' and
                    approval_data.get('agent_id') == agent_id):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to verify approval {approval_id}: {e}")
            return False
    
    async def _get_tools(self) -> List[MCPTool]:
        """Connect to MCP server and get tools."""
        await self.mcp_client.connect()
        tools = await self.mcp_client.list_tools()
        return tools
        
    async def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute tool on MCP server."""
        # Ensure connected
        if not self.mcp_client.process:
            await self.mcp_client.connect()
            
        result = await self.mcp_client.call_tool(tool_name, arguments)
        return result
        
    def run(self):
        """Start the Flask wrapper server."""
        print(f"🚀 MCP Agent Wrapper starting...")
        print(f"   Server: {self.server_name}")
        print(f"   Port: {self.port}")
        print(f"   HITL Required For: {self.require_hitl or 'None'}")
        
        self.app.run(
            host='0.0.0.0',
            port=self.port,
            debug=False
        )


def main():
    """Example usage."""
    # Example: Wrap filesystem MCP server
    wrapper = MCPAgentWrapper(
        mcp_command=["npx", "@modelcontextprotocol/server-filesystem", "/tmp"],
        server_name="filesystem",
        require_hitl_for=["write_file", "delete_file"],
        port=5001
    )
    
    wrapper.run()


if __name__ == "__main__":
    main()
