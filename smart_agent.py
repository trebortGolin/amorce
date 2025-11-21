# --- SMART AGENT (NATP V1.3) ---
# Independent implementation. Does NOT depend on 'nexus' module.
# Handles: Identity (Google Secret Manager), Signing (Ed25519), Discovery, Execution.

import os
import json
import time
import base64
import requests
from uuid import uuid4
from datetime import datetime, timezone

# Cryptography Imports
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from google.cloud import secretmanager

# --- Configuration ---
# We use internal URLs for Cloud Run to Cloud Run communication if needed,
# but external URLs are safer for generic config.
TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL", "https://amorce-trust-api-425870997313.us-central1.run.app")
# Self-reference for loopback calls (Bridge)
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8080")

AGENT_ID = os.environ.get("AGENT_ID", "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "amorce-prod-rgosselin")
SECRET_NAME = os.environ.get("SECRET_NAME", "atp-agent-private-key")

_private_key_cache = None

def _get_key_from_secret_manager():
    """
    Loads the Ed25519 private key from Google Secret Manager.
    """
    global _private_key_cache
    if _private_key_cache:
        return _private_key_cache

    try:
        print(f"🔐 Loading identity from Secret Manager: {SECRET_NAME}...")
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        pem_data = response.payload.data

        _private_key_cache = serialization.load_pem_private_key(
            pem_data,
            password=None,
            backend=default_backend()
        )
        return _private_key_cache
    except Exception as e:
        print(f"❌ CRITICAL: Identity Load Failed: {e}")
        raise e

def sign_message(message_body: dict) -> str:
    """
    Signs a JSON payload using Ed25519. Returns Base64 signature.
    """
    private_key = _get_key_from_secret_manager()
    # Canonicalize JSON (Sort keys is mandatory for consistent signatures)
    canonical_message = json.dumps(message_body, sort_keys=True).encode('utf-8')
    signature = private_key.sign(canonical_message)
    return base64.b64encode(signature).decode('utf-8')

# --- BRIDGE FUNCTIONALITY (FR-O1) ---

def run_bridge_transaction(service_id: str, payload: dict) -> dict:
    """
    Called by the Orchestrator (Bridge Endpoint).
    Acts as a proxy: Signs the intent and sends it to the network.
    """
    print(f"🌉 BRIDGE: Processing request for service {service_id}")

    # 1. Construct the ATP Envelope
    body = {
        "transaction_id": str(uuid4()),
        "service_id": service_id,
        "consumer_agent_id": AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }

    # 2. Sign (L2 Security)
    try:
        signature = sign_message(body)
    except Exception as e:
        return {"error": f"Signing failed: {str(e)}", "status": "failed"}

    # 3. Execute (Loopback to Orchestrator A2A endpoint)
    # Since we are inside the container, we call our own /v1/a2a/transact endpoint
    # Note: In Cloud Run, we might need the full public URL or localhost if within same instance.
    target_url = f"{ORCHESTRATOR_URL}/v1/a2a/transact"
    if "localhost" in ORCHESTRATOR_URL:
         # If generic default, try to use the one from env or fallback
         pass

    headers = {
        "X-Agent-Signature": signature,
        "Content-Type": "application/json",
        "X-API-Key": AGENT_API_KEY
    }

    try:
        # We use the public URL for the call to ensure full path routing
        # For this specific setup, we trust the caller knows ORCHESTRATOR_URL or we use localhost
        # Let's try a robust approach:

        print(f"pw sending to: {target_url}")
        # We need to ensure we hit the correct endpoint.
        # If this runs in the same process as orchestrator, it's a loopback network call.
        response = requests.post(target_url, json=body, headers=headers, timeout=10)

        try:
            return response.json()
        except json.JSONDecodeError:
            return {"error": response.text, "status": "failed", "code": response.status_code}

    except requests.exceptions.RequestException as e:
        return {"error": f"Bridge Connection Failed: {str(e)}", "status": "failed"}

if __name__ == "__main__":
    print("Smart Agent Module Loaded.")