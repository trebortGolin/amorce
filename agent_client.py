import requests
import os
import time
from cryptography.hazmat.primitives import hashes
# Note: PSS Padding was for RSA. Ed25519 doesn't use it.
# from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from google.cloud import secretmanager  # New import
import base64
import json
from uuid import uuid4  # P-3 Import
from datetime import datetime, UTC  # P-3 Import (Fixed)

# --- Configuration ---
# P-1 Endpoint (Legacy test)
ORCHESTRATOR_INVOKE_URL = "https://amorce-api-425870997313.us-central1.run.app/v1/agent/invoke"
# P-3 Endpoint (New)
ORCHESTRATOR_TRANSACT_URL = "https://amorce-api-425870997313.us-central1.run.app/v1/a2a/transact"

# P-4: AGENT_ID is now a static UUID, compliant with Annexe A
# We will use this ID to update our Firestore record (Task 4)
AGENT_ID = os.environ.get("AGENT_ID", "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a")

# L1 Security: API Key for the Orchestrator
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")

# GCP Project ID where the secret is stored.
GCP_PROJECT_ID = "amorce-prod-rgosselin"

# L2 Security: Secret name for our Private Key
SECRET_NAME = "atp-agent-private-key"

# In-memory cache for the private key
_private_key_cache = None


def _get_key_from_secret_manager():
    """
    Fetches the private key from GCP Secret Manager.
    This function is called once on startup.
    """
    global _private_key_cache
    if _private_key_cache:
        return _private_key_cache

    try:
        print(f"Loading private key from Secret Manager: {SECRET_NAME}...")
        client = secretmanager.SecretManagerServiceClient()

        # Build the resource name of the secret version
        name = f"projects/{GCP_PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"

        # Access the secret version
        response = client.access_secret_version(request={"name": name})

        # Extract the PEM data (in bytes)
        pem_data = response.payload.data

        # Load the key from the bytes (Ed25519 key)
        _private_key_cache = serialization.load_pem_private_key(
            pem_data,
            password=None,
            backend=default_backend()
        )
        print("Private key loaded into memory successfully.")
        return _private_key_cache

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load private key from Secret Manager.")
        print(f"Error: {e}")
        raise


def sign_message(message_body: dict) -> str:
    """
    Signs a message body (dict) using the in-memory Ed25519 private key.
    """
    private_key = _get_key_from_secret_manager()

    # The message must be canonicalized for the signature to be consistent.
    canonical_message = json.dumps(message_body, sort_keys=True).encode('utf-8')

    # Ed25519 `sign` method is simple and takes only the message data.
    signature = private_key.sign(
        canonical_message
    )

    # Return the signature as Base64 for HTTP transport
    return base64.b64encode(signature).decode('utf-8')


def send_signed_request(action, text):
    """
    (P-1 Test) Builds, signs, and sends a request to the /invoke endpoint.
    """
    print(f"Sending P-1 request to {ORCHESTRATOR_INVOKE_URL}...")

    body = {
        "agent_id": AGENT_ID,  # P-4: This is now a UUID
        "action": action,
        "text": text,
        "timestamp": int(time.time())
    }

    try:
        signature = sign_message(body)
    except Exception as e:
        print(f"Failed to sign message: {e}")
        return

    headers = {
        "X-Agent-Signature": signature,
        "Content-Type": "application/json"
    }

    if AGENT_API_KEY:
        headers["X-API-Key"] = AGENT_API_KEY
    else:
        print("CRITICAL: AGENT_API_KEY environment variable not set. Request will fail authentication.")
        return

    try:
        response = requests.post(ORCHESTRATOR_INVOKE_URL, json=body, headers=headers, timeout=10)

        if response.status_code == 200:
            print("Orchestrator Response (Success):")
            print(response.json())
        else:
            print(f"Orchestrator Response (Error {response.status_code}):")
            print(response.text)

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to orchestrator: {e}")


def send_a2a_transaction(service_id: str, query: str):
    """
    (P-3 Test) Builds, signs, and sends a TransactionRequest to the /transact endpoint.
    """
    print(f"Sending P-3 A2A request to {ORCHESTRATOR_TRANSACT_URL}...")

    # This body MUST match the TransactionRequest schema (White Paper Sec 3.2)
    body = {
        "transaction_id": str(uuid4()),
        "service_id": service_id,
        "consumer_agent_id": AGENT_ID,  # P-4: This is now a UUID
        # FIX: Use timezone-aware datetime.now(datetime.UTC)
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": {
            "query": query  # This matches the 'input_schema' we created
        }
    }

    try:
        # Sign the *entire* transaction body
        signature = sign_message(body)
    except Exception as e:
        print(f"Failed to sign P-3 transaction: {e}")
        return

    headers = {
        "X-Agent-Signature": signature,  # L2 Security
        "Content-Type": "application/json"
    }

    if AGENT_API_KEY:
        headers["X-API-Key"] = AGENT_API_KEY  # L1 Security
    else:
        print("CRITICAL: AGENT_API_KEY environment variable not set. Request will fail authentication.")
        return

    try:
        response = requests.post(ORCHESTRATOR_TRANSACT_URL, json=body, headers=headers, timeout=10)

        print(f"Orchestrator A2A Response (Status: {response.status_code}):")
        print(response.json())

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to orchestrator (A2A): {e}")


if __name__ == "__main__":
    try:
        # Load key once
        _get_key_from_secret_manager()

        # --- Test P-1 (P-4 VALIDATION) ---
        print("\n--- RUNNING P-1 (INVOKE) TEST (P-4 VALIDATION) ---")
        send_signed_request(
            action="query_nlu",
            text="What is the status of project Nexus?"
        )

        # --- Test P-3 (Commented out) ---
        # print("\n--- RUNNING P-3 (A2A TRANSACT) TEST ---")

        # !!! IMPORTANT !!!
        # Replace this with the Document ID (service_id) you copied from Firestore
        # TEST_SERVICE_ID = "0gY79QjN2M9ex0t8CgL1" # <-- EXAMPLE ID. REPLACE THIS.

        # if "YOUR-FIRESTORE-SERVICE-ID-HERE" in TEST_SERVICE_ID:
        #     print("ERROR: Please update TEST_SERVICE_ID in agent_client.py (line 217)")
        # elif "0gY79QjN2M9ex0t8CgL1" in TEST_SERVICE_ID:
        #     print("WARNING: TEST_SERVICE_ID is still set to the example value.")
        #     print("Please update it to a real Service ID from your 'services' collection in Firestore.")
        #     # We still run the test, but it will likely fail.
        #     send_a2a_transaction(
        #         service_id=TEST_SERVICE_ID,
        #         query="What is the capital of France?"
        #     )
        # else:
        #     send_a2a_transaction(
        #         service_id=TEST_SERVICE_ID,
        #         query="What is the capital of France?"
        #     )

    except Exception as e:
        print(f"Agent failed to start: {e}")