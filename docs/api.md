# API Reference

Complete HTTP API documentation for the Amorce orchestrator.

---

## Base URL

**Standalone Mode**: `http://localhost:8080`  
**Cloud Mode**: `https://your-orchestrator.run.app`

---

## Authentication

### API Key (Optional in Standalone, Required in Cloud)

```http
X-API-Key: sk-atp-your-orchestrator-key
```

### Agent Signature (Always Required)

```http
X-Agent-Signature: <base64-encoded-ed25519-signature>
```

---

## Endpoints

### Agent-to-Agent Transaction

Execute a secure transaction between two agents.

**POST** `/v1/a2a/transact`

**Headers:**
- `Content-Type: application/json`
- `X-API-Key: sk-atp-...` (cloud mode only)
- `X-Agent-Signature: <signature>` (required)

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

**Response (Success):**
```json
{
  "transaction_id": "tx_123",
  "status": "success",
  "timestamp": "2025-12-05T17:00:00Z",
  "result": {
    "message": "Hello, Alice!"
  }
}
```

**Response (Error):**
```json
{
  "transaction_id": "tx_123",
  "status": "error",
  "error": "Invalid signature",
  "timestamp": "2025-12-05T17:00:00Z"
}
```

**Status Codes:**
- `200 OK`: Transaction successful
- `400 Bad Request`: Invalid request format
- `401 Unauthorized`: Invalid signature or API key
- `404 Not Found`: Agent or service not found
- `429 Too Many Requests`: Rate limit exceeded
- `502 Bad Gateway`: Provider agent unreachable
- `504 Gateway Timeout`: Provider agent timeout

---

### Health Check

Check orchestrator health and status.

**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "mode": "standalone",
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

**Status Codes:**
- `200 OK`: Service healthy
- `503 Service Unavailable`: Service degraded

---

### Human-in-the-Loop (HITL) APIs

#### Create Approval Request

**POST** `/api/v1/approvals`

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

**Status Codes:**
- `201 Created`: Approval request created
- `400 Bad Request`: Invalid request
- `409 Conflict`: Approval ID already exists

---

#### Get Approval Status

**GET** `/api/v1/approvals/{approval_id}`

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

**Status Values:**
- `pending`: Awaiting human decision
- `approved`: Human approved
- `rejected`: Human rejected
- `expired`: Timeout reached

**Status Codes:**
- `200 OK`: Approval found
- `404 Not Found`: Approval not found

---

#### Submit Approval Decision

**POST** `/api/v1/approvals/{approval_id}/submit`

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

**Status Codes:**
- `200 OK`: Decision submitted
- `400 Bad Request`: Invalid decision
- `404 Not Found`: Approval not found
- `409 Conflict`: Already decided or expired

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error description",
  "code": "ERROR_CODE",
  "details": {...}
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Malformed request body |
| `INVALID_SIGNATURE` | Signature verification failed |
| `AGENT_NOT_FOUND` | Agent not registered |
| `SERVICE_NOT_FOUND` | Service not registered |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `PROVIDER_UNREACHABLE` | Cannot reach provider agent |
| `PROVIDER_TIMEOUT` | Provider took too long |
| `INTERNAL_ERROR` | Orchestrator error |

---

## Rate Limiting

### Headers

Response includes rate limit info:

```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1638360000
```

### Limits (Cloud Mode)

- **Per Agent**: 20 requests/minute
- **Burst**: 5 requests/second
- **Retry-After**: Included in 429 response

---

## SDK Usage

### Python

```python
from amorce import AmorceClient, IdentityManager

identity = IdentityManager.load_from_pem_file("./agent_private.pem")

client = AmorceClient(
    identity=identity,
    orchestrator_url="http://localhost:8080",
    agent_id="agent-001"
)

# Transaction
result = client.transact(
    service={"service_id": "srv-greet"},
    payload={"name": "Alice"}
)

# HITL approval
approval = client.request_approval(
    summary="Book restaurant",
    details={...},
    timeout_seconds=300
)

status = client.wait_for_approval(approval["approval_id"])
```

### JavaScript

```javascript
const { AmorceClient, IdentityManager } = require('@amorce/sdk');

const identity = Identity Manager.loadFromPemFile('./agent_private.pem');

const client = new AmorceClient({
  identity,
  orchestratorUrl: 'http://localhost:8080',
  agentId: 'agent-001'
});

// Transaction
const result = await client.transact({
  serviceId: 'srv-greet',
  payload: { name: 'Alice' }
});

// HITL approval
const approval = await client.requestApproval({
  summary: 'Book restaurant',
  details: {...},
  timeoutSeconds: 300
});

const status = await client.waitForApproval(approval.approvalId);
```

---

## Webhook Events (Future)

Future versions will support webhooks for:
- Transaction completion
- Approval decisions
- Agent registration
- Service updates

---

## Versioning

API version specified in URL path:

- **Current**: `/v1/...`
- **Future**: `/v2/...`

Version also in response header:

```http
X-AATP-Version: 1.0
```

---

## OpenAPI Specification

Download the complete OpenAPI spec:
```bash
curl http://localhost:8080/openapi.json
```

---

## Examples

### Complete Transaction Flow

```bash
# 1. Generate signature
SIGNATURE=$(python3 -c "from amorce import IdentityManager; import json, base64; identity = IdentityManager.load_from_pem_file('./agent_private.pem'); payload = json.dumps({'consumer_agent_id': 'agent-001', 'service_id': 'srv-greet', 'payload': {'name': 'Alice'}}, separators=(',', ':'), sort_keys=True); sig = identity.sign(payload.encode()); print(base64.b64encode(sig).decode())")

# 2. Execute transaction
curl -X POST http://localhost:8080/v1/a2a/transact \
  -H "Content-Type: application/json" \
  -H "X-Agent-Signature: $SIGNATURE" \
  -d '{
    "consumer_agent_id": "agent-001",
    "service_id": "srv-greet",
    "payload": {"name": "Alice"}
  }'
```

### HITL Approval Flow

```bash
# 1. Create approval
curl -X POST http://localhost:8080/api/v1/approvals \
  -H "Content-Type: application/json" \
  -d '{
    "approval_id": "apr_123",
    "transaction_id": "tx_456",
    "summary": "Book restaurant",
    "details": {...},
    "timeout_seconds": 300
  }'

# 2. Check status
curl http://localhost:8080/api/v1/approvals/apr_123

# 3. Submit decision
curl -X POST http://localhost:8080/api/v1/approvals/apr_123/submit \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approve",
    "approved_by": "user@example.com",
    "comments": "Approved"
  }'
```

---

## Support

- **Documentation**: https://amorce.io/docs
- **GitHub**: https://github.com/trebortGolin/amorce
- **Community**: https://amorce.io/community

---

**API Version**: 1.0  
**Last Updated**: December 2025
