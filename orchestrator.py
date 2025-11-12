# --- ORCHESTRATOR (Amorce P-4) ---
# v1.1 (Security): Added @require_api_key decorator.
# v1.2 (P-3): Added /v1/a2a/transact endpoint.
# v1.3 (P-4): Updated get_public_key to support Annexe A (UUIDs + status check).

import os
import json
import logging
import requests
import base64
import time
from datetime import datetime, UTC  # P-3 Import
from uuid import uuid4  # P-3 Import
from functools import wraps
from typing import Callable, Any, Optional, Dict

# --- Cryptography Imports for Verification ---
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from flask import Flask, request, jsonify, g

# --- Global Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# --- CRITICAL: Load Security Variables ---

# P-1: Load the Trust Directory URL (for key lookup)
TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL")
if not TRUST_DIRECTORY_URL:
    logging.warning("TRUST_DIRECTORY_URL not set. Signature verification will fail.")

# P-0: Load the API Key (for endpoint security)
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")
if not AGENT_API_KEY:
    logging.warning("AGENT_API_KEY environment variable not set. API will be insecure.")


# --- Authentication Decorator (Security Layer 1) ---
def require_api_key(f: Callable) -> Callable:
    """
    Decorator to ensure the 'X-API-Key' header is present and valid.
    This is the first line of defense.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AGENT_API_KEY:
            # If no API_KEY is set on the server, bypass auth (insecure mode)
            logging.warning("Bypassing API key check (server key not set).")
            return f(*args, **kwargs)

        key = request.headers.get('X-API-Key')  # Using a simple key name
        if not key or key != AGENT_API_KEY:
            logging.warning(f"Unauthorized access attempt. Invalid X-API-Key provided.")
            return jsonify({"error": "Unauthorized"}), 401

        g.auth_source = f"Orchestrator (Key: {key[:5]}...)"
        logging.info(f"AUTH_SUCCESS: Valid key received from {g.auth_source}")
        return f(*args, **kwargs)

    return decorated_function


# --- P-1 / P-4: In-Memory Public Key Cache ---
# { "agent_id": (Ed25519PublicKey, timestamp), ... }
PUBLIC_KEY_CACHE: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes, as requested by Athéna


def get_public_key(agent_id: str) -> Optional[ed25519.Ed25519PublicKey]:
    """
    (P-4 Updated) Fetches the public key for a given agent_id (now a UUID).
    Implements P-1: In-memory cache with a 5-minute TTL.
    Implements P-4: Checks the 'status' field from the AgentIdentityRecord.
    """
    if not TRUST_DIRECTORY_URL:
        logging.error("FATAL: TRUST_DIRECTORY_URL is not set. Cannot verify signatures.")
        return None

    # 1. Check cache first
    cached_data = PUBLIC_KEY_CACHE.get(agent_id)
    if cached_data:
        key, timestamp = cached_data
        if (time.time() - timestamp) < CACHE_TTL_SECONDS:
            logging.info(f"Cache HIT for agent '{agent_id}'.")
            return key
        else:
            logging.info(f"Cache STALE for agent '{agent_id}'. Fetching...")

    # 2. If not in cache or stale, fetch from Trust Directory
    #    P-4: The agent_id is now the UUID, which matches the document_id
    #    The old sanitation (replace("/", "_")) is no longer needed.
    document_id = agent_id
    lookup_url = f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{document_id}"

    try:
        logging.info(f"Cache MISS. Fetching public key for '{agent_id}' from: {lookup_url}")
        response = requests.get(lookup_url, timeout=3)

        if response.status_code == 404:
            logging.error(
                f"Signature verification failed: Agent ID '{agent_id}' not found in Trust Directory (404).")
            return None

        if response.status_code != 200:
            logging.error(f"Trust Directory returned status {response.status_code}: {response.text}")
            return None

        data = response.json()

        # --- P-4: New Status Check (Annexe A compliance) ---
        agent_status = data.get("status")
        if agent_status != "active":
            logging.warning(
                f"Signature verification failed: Agent '{agent_id}' is not active (status: {agent_status}).")
            # Cache the failure? For now, just reject.
            return None  # Reject if not active
        # --- End P-4 Check ---

        public_key_pem = data.get("public_key")
        if not public_key_pem:
            logging.error(
                f"Signature verification failed: Trust Directory response for '{agent_id}' missing 'public_key'.")
            return None

        # 3. Load the PEM string into a cryptography object
        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))

        # 4. Store in cache and return
        PUBLIC_KEY_CACHE[agent_id] = (public_key, time.time())
        logging.info(f"Successfully fetched and cached public key for: {agent_id}")
        return public_key

    except requests.exceptions.RequestException as e:
        logging.error(f"Signature verification failed: Could not connect to Trust Directory at {lookup_url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Signature verification failed: Error parsing public key for {agent_id}: {e}")
        return None


# --- API Endpoints ---

@app.route("/v1/agent/invoke", methods=["POST"])
@require_api_key  # L1 Security
def invoke_agent():
    """
    (P-1) This is the main endpoint that our standalone 'agent_client.py' calls.
    (P-4): It now expects agent_id to be a UUID and relies on get_public_key
           to check the agent's 'status'.
    """

    # 1. Get all components of the request
    try:
        body = request.json
        signature_b64 = request.headers.get('X-Agent-Signature')
        agent_id = body.get("agent_id")  # P-4: This will be a UUID
    except Exception as e:
        logging.error(f"Malformed request: {e}")
        return jsonify({"error": "Malformed request."}), 400

    if not all([body, signature_b64, agent_id]):
        logging.error("Zero-Trust Violation: Request is missing 'body', 'signature', or 'agent_id'.")
        return jsonify({"error": "Malformed request."}), 400

    # 2. Get Public Key (using our P-1/P-4 cache function)
    public_key = get_public_key(agent_id)
    if not public_key:
        logging.error(f"Zero-Trust Violation: Could not retrieve or validate public key for agent '{agent_id}'.")
        return jsonify({"error": f"Failed to verify agent identity: {agent_id}"}), 403

        # 3. Verify Signature
    try:
        # 3a. Canonicalize the task data (must match *exactly* how the agent signed it)
        canonical_message = json.dumps(body, sort_keys=True).encode('utf-8')

        # 3b. Decode the signature from Base64
        signature_bytes = base64.b64decode(signature_b64)

        # 3c. Verify! This must be Ed25519
        public_key.verify(signature_bytes, canonical_message)

        logging.info(f"SUCCESS: Signature for agent '{agent_id}' VERIFIED.")

        # 4. Return Success
        return jsonify({
            "status": "Signature verified, task processed (simulation).",
            "received_action": body.get("action")
        }), 200

    except InvalidSignature:
        logging.critical(f"FATAL: ZERO-TRUST VIOLATION! Invalid signature for agent '{agent_id}'.")
        return jsonify({"error": "Invalid signature."}), 401
    except Exception as e:
        logging.error(f"Error during signature verification: {e}", exc_info=True)
        return jsonify({"error": "A critical error occurred during signature verification."}), 500


# --- P-3: New Endpoint for A2A Negotiation ---

@app.route("/v1/a2a/transact", methods=["POST"])
@require_api_key  # L1 Security (API Key)
def a2a_transact():
    """
    (P-3) Handles A2A (Agent-to-Agent) transactions per White Paper Sec 3.2.
    (P-4): It now expects consumer_agent_id to be a UUID and relies on
           get_public_key to check the agent's 'status'.
    """

    # 1. Get all components of the request
    try:
        # The body *is* the TransactionRequest (Sec 3.2)
        body = request.json
        signature_b64 = request.headers.get('X-Agent-Signature')
        # The consumer_agent_id is the identity we must verify
        agent_id = body.get("consumer_agent_id")  # P-4: This will be a UUID
    except Exception as e:
        logging.error(f"Malformed A2A request: {e}")
        return jsonify({"error": "Malformed request."}), 400

    if not all([body, signature_b64, agent_id]):
        logging.error("Zero-Trust Violation (A2A): Request is missing 'body', 'signature', or 'consumer_agent_id'.")
        return jsonify({"error": "Malformed A2A request."}), 400

    # 2. Get Public Key (using our P-1/P-4 cache function)
    # This fulfills Athéna's "Non-Negotiable Condition"
    public_key = get_public_key(agent_id)
    if not public_key:
        logging.error(f"Zero-Trust Violation (A2A): Could not retrieve or validate public key for agent '{agent_id}'.")
        return jsonify({"error": f"Failed to verify agent identity: {agent_id}"}), 403

    # 3. Verify Signature (L2)
    try:
        # 3a. Canonicalize the message (the full body)
        canonical_message = json.dumps(body, sort_keys=True).encode('utf-8')
        # 3b. Decode the signature
        signature_bytes = base64.b64decode(signature_b64)
        # 3c. Verify!
        public_key.verify(signature_bytes, canonical_message)

        logging.info(f"SUCCESS (A2A): Signature for agent '{agent_id}' VERIFIED.")

        # 4. Return Simulated Success Response (TransactionResponse - Sec 3.2)
        simulated_response = {
            "transaction_id": body.get("transaction_id"),
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),  # P-4: Use timezone-aware
            "result": {
                "confirmation": "Service executed successfully (simulation).",
                "provider_agent_id": "amorce-api"  # Self-identify
            },
            "error_message": None
        }
        return jsonify(simulated_response), 200

    except InvalidSignature:
        logging.critical(f"FATAL: ZERO-TRUST VIOLATION (A2A)! Invalid signature for agent '{agent_id}'.")
        return jsonify({"error": "Invalid signature."}), 401
    except Exception as e:
        logging.error(f"Error during A2A signature verification: {e}", exc_info=True)
        return jsonify({"error": "A critical error occurred during signature verification."}), 500


# --- Application Startup ---
if __name__ == '__main__':
    logging.info("Flask Orchestrator (P-4 Annexe A Ready) initialized successfully.")
    # Note: Flask's 'run' is only for local dev.
    app.run(debug=True, port=int(os.environ.get('PORT', 8080)), host='0.0.0.0')