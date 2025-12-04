# MCP (Model Context Protocol) Wrapper for Amorce

## Overview

The MCP wrapper allows you to expose Model Context Protocol servers as Amorce agents, making MCP tools and resources accessible through the AATP protocol with cryptographic signatures and Human-in-the-Loop (HITL) support.

## Quick Start

### 1. Install MCP Server

```bash
# Example: Install filesystem MCP server
npm install -g @modelcontextprotocol/server-filesystem
```

### 2. Configure MCP Server

Edit `config/mcp_servers.json`:

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": ["npx", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "agent_id": "agent-mcp-filesystem",
      "description": "File system operations",
      "require_hitl_for": ["write_file", "delete_file"],
      "enabled": true,
      "port": 5001
    }
  ]
}
```

### 3. Start MCP Wrapper

```bash
# List available servers
python run_mcp_wrappers.py --list

# Start specific server
python run_mcp_wrappers.py filesystem
```

### 4. Call MCP Tools via Amorce

```python
from amorce import IdentityManager
from amorce.mcp_helpers import MCPToolClient

# Create identity
identity = IdentityManager.generate_ephemeral()

# Initialize MCP client
mcp = MCPToolClient(identity)

# Call tool (no approval needed)
result = mcp.call_tool(
    server_name='filesystem',
    tool_name='read_file',
    arguments={'path': '/tmp/test.txt'}
)

print(result)
```

## HITL Example

```python
# Request approval for write operation
approval_id = mcp.request_tool_approval(
    server_name='filesystem',
    tool_name='write_file',
    arguments={'path': '/tmp/important.txt', 'content': 'Hello World'},
    summary="Write to important file"
)

# Human approves via UI or API...

# Execute with approval
result = mcp.call_tool(
    server_name='filesystem',
    tool_name='write_file',
    arguments={'path': '/tmp/important.txt', 'content': 'Hello World'},
    approval_id=approval_id
)
```

## Available MCP Servers

### Filesystem
- **Package:** `@modelcontextprotocol/server-filesystem`
- **Tools:** read_file, write_file, list_directory, search_files
- **Use Case:** File operations with HITL for writes/deletes

### Brave Search
- **Package:** `@modelcontextprotocol/server-brave-search`
- **Tools:** web_search
- **Use Case:** Web search without HITL
- **Setup:** Requires `BRAVE_API_KEY` environment variable

### PostgreSQL
- **Package:** `@modelcontextprotocol/server-postgres`
- **Tools:** query, execute
- **Use Case:** Database access with HITL for mutations

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────┐
│  Amorce Agent   │  AATP   │  MCP Wrapper     │   MCP   │  MCP Server │
│  (Your code)    │────────▶│  (Bridge)        │────────▶│  (filesystem)│
└─────────────────┘         └──────────────────┘         └─────────────┘
     Signatures                Translation              JSON-RPC
     HITL                      Flask Server             STDIO
```

## Benefits

- ✅ **Security:** AATP cryptographic signatures on all MCP tool calls
- ✅ **Governance:** HITL for sensitive operations (file writes, DB changes)
- ✅ **Ecosystem:** Access to 80+ existing MCP servers
- ✅ **Zero Trust:** No API keys needed between agents
- ✅ **Auditability:** All tool calls logged via Amorce

## Configuration Reference

```json
{
  "name": "server_name",           // Unique server identifier
  "command": ["cmd", "args"],      // Command to start MCP server
  "agent_id": "agent-mcp-name",    // Amorce agent ID
  "description": "...",            // Human-readable description
  "require_hitl_for": ["tool"],    // Tools requiring approval
  "enabled": true,                 // Auto-start on launch
  "port": 5001,                    // Flask wrapper port
  "env": {                         // Optional environment variables
    "API_KEY": "${ENV_VAR}"
  }
}
```

## Troubleshooting

### MCP Server Won't Start

```bash
# Test MCP server directly
npx @modelcontextprotocol/server-filesystem /tmp

# Check if port is available
lsof -i :5001
```

### Tool Call Fails

```python
# List available tools first
tools = mcp.list_tools('filesystem')
print(tools)

# Check tool name and arguments match schema
```

### HITL Not Triggering

1. Verify tool is in `require_hitl_for` list
2. Check wrapper logs for approval requirements
3. Ensure approval_id is passed when calling after approval

## Resources

- [MCP Specification](https://modelcontextprotocol.io)
- [Available MCP Servers](https://github.com/modelcontextprotocol/servers)
- [Amorce Documentation](../README.md)
