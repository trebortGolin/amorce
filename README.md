# 🤖 Amorce - Agent Transaction Protocol Runtime

**The open-source runtime for secure AI agent-to-agent transactions.**

Amorce is like Docker for AI agents: run it locally for development, or use Amorce Cloud for production hosting.

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Python 3.11+
- No cloud accounts needed

### 1. Install

```bash
# Clone the repository
git clone https://github.com/trebortGolin/amorce.git
cd amorce

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Amorce SDK
pip install -e ../amorce_py_sdk
```

### 2. Create Local Configuration

```bash
# Copy example config files
cp config/agents.json.example config/agents.json
cp config/services.json.example config/services.json
cp .env.example .env
```

### 3. Run Locally

```bash
# Start the orchestrator in standalone mode
python orchestrator.py
# Server running at http://localhost:8080
```

That's it! Your local Amorce runtime is ready.

---

## 🏗️ Architecture

Amorce is a **modular runtime** with pluggable components:

```
┌─────────────────────────────────┐
│   Your AI Agent Application     │
└─────────────┬───────────────────┘
              │ AATP Messages
┌─────────────▼───────────────────┐
│      Amorce Runtime Core        │
│  ┌────────────────────────────┐ │
│  │  Signature Verification    │ │
│  │  Message Routing           │ │
│  │  Protocol Validation       │ │
│  └────────────────────────────┘ │
└─────────────┬───────────────────┘
              │
        ┌─────┴──────┐
        │            │
   ┌────▼────┐  ┌────▼────┐
   │  Local  │  │  Cloud  │
   │  Mode   │  │  Mode   │
   └─────────┘  └─────────┘
```

### Core Components

- **Core:** Pure AATP protocol logic (signatures, message formats)
- **Adapters:** Pluggable Registry, Storage, and Rate Limiting
  - **Local:** File-based registry, SQLite storage, no rate limits
  - **Cloud:** Trust Directory API, Firestore, Redis
- **Modes:** Standalone (default) or Cloud (optional)

---

## 📖 Usage Modes

### Standalone Mode (Default)

Perfect for development and self-hosting. Uses local configuration files.

```bash
# .env
AMORCE_MODE=standalone

# Run
python orchestrator.py
```

**What it uses:**
- `config/agents.json` - Agent registry (public keys, endpoints)
- `config/services.json` - Service contracts
- `data/transactions.db` - SQLite transaction logs

**No cloud dependencies required.**

### Cloud Mode (Optional)

Connect to Amorce Cloud for global agent discovery and managed services.

```bash
# .env
AMORCE_MODE=cloud
TRUST_DIRECTORY_URL=https://amorce-trust-api.run.app
AGENT_API_KEY=sk-atp-your-key

# Install cloud dependencies
pip install -r requirements-cloud.txt

# Run
python orchestrator.py
```

**What it uses:**
- Amorce Trust Directory (agent registry)
- Google Cloud Firestore (metering)
- Redis (rate limiting)

---

## 🔌 Building Your First Agent

### 1. Create a Simple Agent

```python
# my_agent.py
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/greet', methods=['POST'])
def greet():
    data = request.json.get('data', {})
    name = data.get('name', 'stranger')
    return jsonify({"message": f"Hello, {name}!"})

if __name__ == '__main__':
    app.run(port=5001)
```

### 2. Generate Identity Keys

```python
# generate_keys.py
from amorce import IdentityManager

identity = IdentityManager.generate()

print(f"Agent ID: {identity.agent_id}")
print(f"\nPublic Key:\n{identity.get_public_key_pem()}")
print(f"\nPrivate Key:\n{identity.get_private_key_pem()}")
print("\n⚠️  Save your private key securely!")
```

### 3. Register in Local Config

Add to `config/agents.json`:

```json
{
  "your-agent-id": {
    "agent_id": "your-agent-id",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "metadata": {
      "name": "My Agent",
      "api_endpoint": "http://localhost:5001",
      "status": "active"
    }
  }
}
```

### 4. Create a Service Contract

Add to `config/services.json`:

```json
{
  "srv-greet": {
    "service_id": "srv-greet",
    "provider_agent_id": "your-agent-id",
    "metadata": {
      "service_path_template": "/greet"
    }
  }
}
```

### 5. Test the Transaction

```python
from amorce import AmorceClient, IdentityManager

# Your agent's identity
identity = IdentityManager.load_from_pem_file("./agent_private_key.pem")

# Initialize client
client = AmorceClient(
    identity=identity,
    orchestrator_url="http://localhost:8080",
    agent_id="your-agent-id"
)

# Execute transaction
service = {"service_id": "srv-greet"}
payload = {"name": "Alice"}

result = client.transact(service, payload)
print(result)  # {"message": "Hello, Alice!"}
```

---

## 🌐 Usage Scenarios

### Local Development
Two agents on your laptop talking securely:
```bash
# Terminal 1: Start orchestrator
python orchestrator.py

# Terminal 2: Start agent A
python agent_a.py

# Terminal 3: Start agent B
python agent_b.py

# Terminal 4: Test transaction
python test_transaction.py
```

### Self-Hosting
Deploy on your own infrastructure:
```bash
# Using Docker
docker build -t amorce .
docker run -p 8080:8080 \
  -e AMORCE_MODE=standalone \
  -v ./config:/app/config \
  amorce

# Using Cloud Run / AWS / Azure
# See docs/deployment.md
```

### Amorce Cloud
Use our managed service:
```bash
# Sign up at amorce.io
# Get your API key
export AMORCE_MODE=cloud
export AGENT_API_KEY=sk-atp-...
python orchestrator.py
```

---

## 📚 Documentation

- [Building Agents](./docs/building-agents.md) - Step-by-step guide
- [Protocol Specification](./docs/protocol.md) - AATP details
- [Deployment Guide](./docs/deployment.md) - Self-hosting
- [API Reference](./docs/api.md) - HTTP endpoints

---

## 🛡️ Security Model (Zero-Trust)

### L1: API Key Authentication

```http
POST /v1/a2a/transact
X-API-Key: sk-atp-your-key
```

Optional in standalone mode, required in cloud mode.

### L2: Cryptographic Signatures

All transactions are signed with Ed25519:

1. Consumer signs transaction payload
2. Signature sent in `X-Agent-Signature` header
3. Orchestrator fetches public key from registry
4. Signature verified against canonical JSON
5. Request routed only if valid

### L3: Rate Limiting

- **Standalone:** Disabled (dev mode)
- **Cloud:** Redis-backed (10 req/min default)

---

## 📡 API Endpoints

### Agent-to-Agent Transaction

**POST** `/v1/a2a/transact`

Routes transactions between agents with signature verification.

**Headers:**
- `X-API-Key` - Orchestrator API key (optional in standalone)
- `X-Agent-Signature` - Ed25519 signature (base64)

**Request Body:**
```json
{
  "consumer_agent_id": "agent-001",
  "service_id": "srv-greet",
  "payload": {
    "name": "Alice"
  },
  "transaction_id": "tx_123" 
}
```

**Response:**
```json
{
  "transaction_id": "tx_123",
  "status": "success",
  "timestamp": "2025-12-01T12:00:00Z",
  "result": {
    "message": "Hello, Alice!"
  }
}
```

### Health Check

**GET** `/health`

```json
{
  "status": "healthy",
  "mode": "standalone",
  "version": "1.0.0"
}
```

### Human-in-the-Loop (HITL) Approvals

Amorce includes built-in support for human oversight of agent decisions.

#### Create Approval Request

**POST** `/api/v1/approvals`

Create an approval request that requires human review.

**Request Body:**
```json
{
  "approval_id": "apr_custom_id",
  "transaction_id": "tx_123",
  "summary": "Book restaurant for 4 guests at Le Petit Bistro",
  "details": {
    "restaurant": "Le Petit Bistro",
    "guests": 4,
    "date": "2025-12-05",
    "time": "19:00"
  },
  "timeout_seconds": 300
}
```

**Response:**
```json
{
  "approval_id": "apr_custom_id",
  "status": "pending",
  "created_at": "2025-12-02T17:00:00Z",
  "expires_at": "2025-12-02T17:05:00Z"
}
```

#### Get Approval Status

**GET** `/api/v1/approvals/{approval_id}`

Check the current status of an approval request.

**Response:**
```json
{
  "approval_id": "apr_custom_id",
  "transaction_id": "tx_123",
  "status": "approved",
  "summary": "Book restaurant for 4 guests",
  "details": {...},
  "decision": "approve",
  "approved_by": "user@example.com",
  "approved_at": "2025-12-02T17:02:00Z",
  "comments": "Looks good"
}
```

**Status values:** `pending`, `approved`, `rejected`, `expired`

#### Submit Approval Decision

**POST** `/api/v1/approvals/{approval_id}/submit`

Submit a human decision for an approval request.

**Request Body:**
```json
{
  "decision": "approve",
  "approved_by": "user@example.com",
  "comments": "Approved for business lunch"
}
```

**Response:**
```json
{
  "approval_id": "apr_custom_id",
  "status": "approved",
  "approved_at": "2025-12-02T17:02:00Z"
}
```


---

## 🚀 Advanced: Production Deployment

### Docker

```bash
# Build
docker build -t amorce:latest .

# Run (standalone)
docker run -p 8080:8080 \
  -v ./config:/app/config \
  -v ./data:/app/data \
  amorce:latest

# Run (cloud)
docker run -p 8080:8080 \
  -e AMORCE_MODE=cloud \
  -e TRUST_DIRECTORY_URL=https://... \
  -e AGENT_API_KEY=sk-atp-... \
  amorce:latest
```

### Google Cloud Run

```bash
gcloud builds submit --config cloudbuild.yaml \
  --project your-project \
  --substitutions=_TAG_VERSION=v1.0.0
```

### Custom Registry

Implement `IAgentRegistry` for your own directory:

```python
from core.interfaces import IAgentRegistry

class MyCustomRegistry(IAgentRegistry):
    def find_agent(self, agent_id: str):
        # Your implementation
        pass
```

---

## 🤝 Contributing

Amorce is open source. We welcome:
- Protocol improvements
- New adapter implementations  
- Bug fixes and documentation

See [CONTRIBUTING.md](./CONTRIBUTING.md)

---

## 📄 License

MIT License - See [LICENSE](./LICENSE)

---

## 🌐 Amorce Cloud (Optional)

Don't want to manage infrastructure? Use Amorce Cloud:

- ✅ Global agent registry
- ✅ Automatic scaling
- ✅ Built-in monitoring
- ✅ Pay-as-you-go billing

[Sign up at amorce.io](https://amorce.io)

---

## 📊 Protocol

Implements **AATP v1.0.0** (Amorce Agent Transaction Protocol):
- Ed25519 signatures (L2 security)
- Canonical JSON serialization (RFC 8785)
- Trust Directory verification
- Fail-safe error handling

---


---

## 🔌 MCP Wrapper - Production Ready ✅

**Status:** 95-100% Production Ready | Comprehensively Tested | Deployment Ready

The MCP wrapper exposes [Model Context Protocol](https://modelcontextprotocol.io) servers as secure Amorce agents, adding cryptographic security and human-in-the-loop (HITL) oversight to MCP tool calls.

### 🚀 Quick Start

```bash
# 1. Start in production mode
AMORCE_ENV=production python3 run_mcp_wrappers.py filesystem

# 2. Call MCP tools with security
from amorce import IdentityManager, MCPToolClient

identity = IdentityManager.generate_ephemeral()
mcp = MCPToolClient(identity, "http://localhost:5001")

# Read file (no approval needed)
result = mcp.call_tool('filesystem', 'read_file', {'path': '/tmp/data.txt'})

# Write file (requires HITL approval)
approval_id = mcp.request_approval('filesystem', 'write_file', {...})
result = mcp.call_tool('filesystem', 'write_file', {'path': '/tmp/output.txt'}, approval_id)
```

### ✅ Production Features

- **🔐 Security:** Ed25519 cryptographic signatures on every tool call
- **👤 HITL:** Human approval required for sensitive operations (write, delete, move)
- **⚡ Performance:** 3-9ms response times, handles 50 concurrent requests
- **🛡️ Rate Limiting:** 20 req/min per endpoint, configurable
- **🏭 Production Server:** Gunicorn with 4 workers, load-tested and stable
- **📊 Monitoring:** Enhanced health checks with MCP server status
- **🌐 Ecosystem:** Access to 80+ MCP servers (filesystem, search, databases, APIs)

### 📈 Performance Metrics

**Load Tested & Validated:**
- **Concurrent Requests:** 50 requests in 40ms
- **Response Times:** 3-9ms average, 5ms median
- **Rate Limiting:** 20 req/min enforced, 48% throttled at peak
- **Stability:** Zero crashes under sustained load
- **HITL Workflow:** Complete approval flow <100ms

### 🔧 Deployment Options

**Option 1: Standalone Mode (Development/Staging)**
```bash
# Quick start - no trust directory needed
AMORCE_ENV=production python3 run_mcp_wrappers.py filesystem
```

**Option 2: Full Production Mode**
```bash
# With trust directory integration
AMORCE_ENV=production \
TRUST_DIRECTORY_URL=https://trust.amorce.io \
python3 run_mcp_wrappers.py filesystem
```

### 📦 Available MCP Servers

- **filesystem** - Read/write files, list directories (production-ready)
- **search** - Web search with approval controls
- **database** - PostgreSQL, MySQL with HITL protection
- **git** - Repository operations with human oversight
- [80+ more servers](https://github.com/modelcontextprotocol/servers)

### 📚 Documentation

- **[Complete Guide](docs/MCP_WRAPPER.md)** - Architecture, deployment, examples
- **[SDK Integration](/Users/rgosselin/amorce_py_sdk/README.md#mcp-integration)** - Client usage
- **[Console Docs](https://amorce.io/docs/guides/mcp-integration)** - UI integration
- **[Test Results](tests/TEST_RESULTS.md)** - Comprehensive test evidence

### 🎯 Production Ready

Comprehensively tested across 5 phases:
- ✅ MCP Connection (14 tools discovered)
- ✅ Signed Requests (complete flow working)
- ✅ HITL Workflow (files written with approval)
- ✅ Load Testing (50 concurrent, stable)
- ✅ Trust Directory (95% integration complete)

**Ready for deployment to production environments.**


## 📚 Related Projects

- [amorce_py_sdk](https://github.com/trebortGolin/amorce_py_sdk) - Python SDK
- [amorce-js-sdk](https://github.com/trebortGolin/amorce-js-sdk) - JavaScript SDK
- [amorce-trust-directory](https://github.com/trebortGolin/amorce-trust-directory) - Agent registry
- [amorce-console](https://github.com/trebortGolin/amorce-console) - Management UI

---

**Built with ❤️ by the Amorce team**