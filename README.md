# 🤖 Amorce Orchestrator

**Amorce orchestrator** is the reference implementation of the **Amorce Agent Transaction Protocol (AATP)**. It provides a secure, zero-trust orchestration layer for AI agent-to-agent transactions.

---

## 🏛️ Architecture

The orchestrator is deployed as a containerized service on Google Cloud Run and consists of:

### Core Components

**`orchestrator.py`** 🔑 (The "Router")
- Flask API layer handling L1 authentication (`X-API-Key`)
- L2 cryptographic signature verification (Ed25519)
- Rate limiting via Redis
- Transaction routing to provider agents
- Metering and logging to Firestore

**`smart_agent.py`** 🧠 (The "Brain")
- Agent logic layer with Gemini AI integration
- Bridge endpoint for no-code tool integrations
- Implements Amorce client for secure transactions

### Dependencies

- **Amorce Python SDK** (`amorce-sdk`) - Cryptographic primitives and client
- **Google Cloud Services** - Firestore, Secret Manager, Cloud Run
- **Redis** - Rate limiting and caching
- **Flask** - Web framework

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites

- Python 3.11+
- Virtual environment
- Google Cloud Project with Firestore and Secret Manager enabled

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/trebortGolin/amorce.git
cd amorce

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install the Amorce SDK (from parent directory)
pip install -e ../amorce_py_sdk
```

### 3. Configuration

Create a `.env` file with the following variables:

```bash
# Trust Directory (Agent Registry)
TRUST_DIRECTORY_URL="https://amorce-trust-api-425870997313.us-central1.run.app"

# API Authentication
AGENT_API_KEY="sk-atp-amorce-2025-<your-key>"

# Agent Identity (for smart_agent.py)
AGENT_ID="<your-agent-uuid>"
GCP_PROJECT_ID="amorce-prod-rgosselin"
SECRET_NAME="atp-agent-private-key"

# LLM Integration (for smart_agent.py)
GOOGLE_API_KEY="AIzaSy<your-gemini-key>"

# Redis Configuration (optional for local dev)
REDIS_HOST="localhost"
REDIS_PORT="6379"
```

### 4. Launch Locally

```bash
# Start the orchestrator
python orchestrator.py

# The server will be available at http://127.0.0.1:8080
```

---

## ☁️ Production Deployment (Google Cloud Run)

### Build and Deploy

The orchestrator is deployed using Cloud Build:

```bash
# Deploy using Cloud Build
gcloud builds submit --config cloudbuild.yaml \
  --project amorce-prod-rgosselin \
  --substitutions=_TAG_VERSION=v2.0.0
```

### Environment Configuration

The following environment variables are set in `cloudbuild.yaml`:

- `TRUST_DIRECTORY_URL` - Agent registry endpoint
- `AGENT_API_KEY` - API authentication key
- `AGENT_ID` - Smart agent UUID
- `GCP_PROJECT_ID` - Google Cloud project
- `SECRET_NAME` - Private key in Secret Manager
- `REDIS_HOST` - Internal Redis IP (via VPC connector)

### VPC Configuration

The orchestrator connects to Redis via VPC connector:
- VPC Connector: `amorce-vpc-connector`
- Redis IP: `10.185.13.251`

---

## 🛡️ Security Model (Zero-Trust)

### L1: API Key Authentication

```http
POST /v1/a2a/transact
X-API-Key: sk-atp-amorce-2025-<key>
```

The orchestrator validates the API key before processing requests.

### L2: Cryptographic Signatures

All transactions are signed with Ed25519 private keys:

1. Consumer agent signs transaction payload
2. Signature sent in `X-Agent-Signature` header
3. Orchestrator fetches consumer's public key from Trust Directory
4. Signature verified against canonical JSON payload
5. Request routed to provider only if  signature valid

### L3: Rate Limiting

Redis-based rate limiting:
- 10 requests per minute per agent ID
- Fail-open design (allows traffic if Redis down)

---

## 📡 API Endpoints

### Agent-to-Agent Transaction

**POST** `/v1/a2a/transact`

Routes transactions between agents with signature verification.

**Headers:**
- `X-API-Key` - Orchestrator API key
- `X-Agent-Signature` - Ed25519 signature (base64)

**Request Body:**
```json
{
  "service_id": "srv_<uuid>",
  "consumer_agent_id": "<agent-id>",
  "payload": {
    "intent": "book_reservation",
    "params": {"date": "2025-12-01", "guests": 2}
  },
  "priority": "normal"
}
```

### Bridge Endpoint (No-Code Tools)

**POST** `/v1/amorce/bridge`

Simplified endpoint for no-code integrations (Zapier, Make, etc.).

---

## 🔧 Development

### Project Structure

```
amorce/
├── orchestrator.py       # Main routing service
├── smart_agent.py        # AI agent logic
├── Dockerfile           # Container configuration
├── cloudbuild.yaml      # CI/CD configuration
├── requirements.txt     # Python dependencies
└── amorce_py_sdk/      # Local Amorce SDK copy
```

### Running Tests

```bash
# Run unit tests (if available)
python -m pytest tests/

# Test endpoint locally
curl -X POST http://localhost:8080/v1/a2a/transact \
  -H "X-API-Key: sk-atp-amorce-dev" \
  -H "X-Agent-Signature: <base64-signature>" \
  -d '{"service_id": "srv_test", "consumer_agent_id": "test", "payload": {}}'
```

---

## 📚 Related Projects

- [amorce_py_sdk](https://github.com/trebortGolin/amorce_py_sdk) - Python SDK for AATP
- [amorce-js-sdk](https://github.com/trebortGolin/amorce-js-sdk) - JavaScript SDK for AATP
- [amorce-trust-directory](https://github.com/trebortGolin/amorce-trust-directory) - Agent registry
- [amorce-console](https://github.com/trebortGolin/amorce-console) - Management console

---

## 📝 Protocol

Implements **AATP v0.1.0** (Amorce Agent Transaction Protocol):
- Ed25519 signatures
- Canonical JSON serialization (RFC 8785)
- Priority lanes (normal, high, critical)
- Trust Directory verification

---

## 📄 License

MIT License

---

## 🚀 Live Service

**Production Endpoint:** https://natp-425870997313.us-central1.run.app

**Status:** ✅ Running with Amorce SDK v2.0.0