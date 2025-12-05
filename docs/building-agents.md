# Building Agents with Amorce

This guide walks you through building production-ready AI agents using the Amorce Agent Transaction Protocol (AATP).

---

## Prerequisites

- Python 3.11+
- Basic understanding of REST APIs
- An AI agent framework (Flask, FastAPI, n8n, or custom)

---

## Step 1: Generate Agent Identity

Every Amorce agent needs a cryptographic identity (Ed25519 keypair).

```python
from amorce import IdentityManager

# Generate new identity
identity = IdentityManager.generate()

# Display credentials
print(f"Agent ID: {identity.agent_id}")
print(f"\nPublic Key:\n{identity.get_public_key_pem()}")
print(f"\nPrivate Key:\n{identity.get_private_key_pem()}")

# Save for later use
identity.save_to_pem_files("./agent_private.pem", "./agent_public.pem")
```

⚠️ **Important**: Keep your private key secure. Anyone with it can impersonate your agent.

---

## Step 2: Build Your Agent API

Agents expose HTTP endpoints that other agents can call. Here's a simple example:

### Flask Example

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/greet', methods=['POST'])
def greet():
    """Simple greeting service"""
    data = request.json.get('data', {})
    name = data.get('name', 'stranger')
    return jsonify({"message": f"Hello, {name}!"})

@app.route('/calculate', methods=['POST'])
def calculate():
    """Basic calculator service"""
    data = request.json.get('data', {})
    operation = data.get('operation')
    a = data.get('a', 0)
    b = data.get('b', 0)
    
    if operation == 'add':
        result = a + b
    elif operation == 'subtract':
        result = a - b
    else:
        return jsonify({"error": "Unsupported operation"}), 400
    
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
```

### FastAPI Example

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class GreetRequest(BaseModel):
    name: str = "stranger"

class CalculateRequest(BaseModel):
    operation: str
    a: float
    b: float

@app.post("/greet")
def greet(req: GreetRequest):
    return {"message": f"Hello, {req.name}!"}

@app.post("/calculate")
def calculate(req: CalculateRequest):
    if req.operation == "add":
        return {"result": req.a + req.b}
    elif req.operation == "subtract":
        return {"result": req.a - req.b}
    else:
        return {"error": "Unsupported operation"}
```

---

## Step 3: Register Your Agent

### Local Registration (Development)

Add your agent to `config/agents.json`:

```json
{
  "agent-001": {
    "agent_id": "agent-001",
    "public_key": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA...\n-----END PUBLIC KEY-----",
    "metadata": {
      "name": "My Greeting Agent",
      "api_endpoint": "http://localhost:5001",
      "status": "active",
      "category": "CUSTOMER_SERVICE"
    }
  }
}
```

### Cloud Registration (Production)

Register via the Amorce Console:

1. Go to https://amorce.io/register
2. Fill in agent details
3. Upload your public key
4. Get your Agent ID

---

## Step 4: Create Service Contracts

Define what services your agent offers in `config/services.json`:

```json
{
  "srv-greet": {
    "service_id": "srv-greet",
    "provider_agent_id": "agent-001",
    "metadata": {
      "name": "Greeting Service",
      "description": "Greets users by name",
      "service_path_template": "/greet",
      "method": "POST"
    }
  },
  "srv-calculate": {
    "service_id": "srv-calculate",
    "provider_agent_id": "agent-001",
    "metadata": {
      "name": "Calculator Service",
      "description": "Basic arithmetic operations",
      "service_path_template": "/calculate",
      "method": "POST"
    }
  }
}
```

---

## Step 5: Test Your Agent

### Using the Amorce SDK

```python
from amorce import AmorceClient, IdentityManager

# Load your agent's identity
identity = IdentityManager.load_from_pem_file("./agent_private.pem")

# Create client
client = AmorceClient(
    identity=identity,
    orchestrator_url="http://localhost:8080",
    agent_id="agent-001"
)

# Call a service
service = {"service_id": "srv-greet"}
payload = {"name": "Alice"}

result = client.transact(service, payload)
print(result)  # {"message": "Hello, Alice!"}
```

### Manual Testing

```bash
# Start orchestrator
python orchestrator.py

# Start your agent
python my_agent.py

# Test transaction
curl -X POST http://localhost:8080/v1/a2a/transact \
  -H "Content-Type: application/json" \
  -H "X-Agent-Signature: <signature>" \
  -d '{
    "consumer_agent_id": "agent-001",
    "service_id": "srv-greet",
    "payload": {"name": "Bob"}
  }'
```

---

## Step 6: Add Human-in-the-Loop (Optional)

For sensitive operations, add human approval:

```python
from amorce import AmorceClient

client = AmorceClient(...)

# Request approval
approval = client.request_approval(
    summary="Book restaurant for 4 guests",
    details={
        "restaurant": "Le Petit Bistro",
        "guests": 4,
        "date": "2025-12-05"
    },
    timeout_seconds=300
)

# Wait for human decision
status = client.wait_for_approval(approval["approval_id"])

if status["decision"] == "approve":
    # Proceed with transaction
    result = client.transact(service, payload)
else:
    # Handle rejection
    print(f"Request rejected: {status.get('comments')}")
```

---

## Best Practices

### Security
- ✅ Never expose your private key
- ✅ Use HTTPS in production
- ✅ Validate all incoming requests
- ✅ Implement rate limiting

### Error Handling
```python
from amorce import TransactionError

try:
    result = client.transact(service, payload)
except TransactionError as e:
    print(f"Transaction failed: {e}")
```

### Logging
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/greet', methods=['POST'])
def greet():
    logger.info("Received greet request")
    # ... handle request
```

---

## Next Steps

- Read the [Protocol Specification](./protocol.md)
- Learn about [Deployment](./deployment.md)
- Check the [API Reference](./api.md)
- Join the community at https://amorce.io

---

**Built with ❤️ by the Amorce team**
