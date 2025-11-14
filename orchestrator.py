# --- ORCHESTRATOR (Amorce P-6-FSA) ---
# v1.1 (Security): Added @require_api_key decorator.
# v1.3 (P-4): Updated get_public_key to support Annexe A (UUIDs + status check).
# v1.4 (P-5): Implemented internal A2A routing logic.
# v1.5 (P-6): Updated A2A routing to proxy to external APIs (Fake Store API).

import os
import json
import logging
import requests
import base64
import time
from datetime import datetime, UTC
from uuid import uuid4
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


# --- P-1 / P-4 / P-5: In-Memory Caching ---

# { "agent_id_uuid": (Ed25519PublicKey, timestamp), ... }
PUBLIC_KEY_CACHE: Dict[str, tuple] = {}
# { "agent_id_uuid": (AgentIdentityRecord_dict, timestamp), ... }
AGENT_RECORD_CACHE: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes, as requested by Athéna


def get_agent_record(agent_id: str) -> Optional[dict]:
    """
    (P-5.2) Fetches the full AgentIdentityRecord from the Trust Directory.
    Implements P-1: In-memory cache with a 5-minute TTL.
    Implements P-4: Checks the 'status' field.
    """
    if not TRUST_DIRECTORY_URL:
        logging.error("FATAL: TRUST_DIRECTORY_URL is not set. Cannot verify signatures.")
        return None

    # 1. Check cache first
    cached_data = AGENT_RECORD_CACHE.get(agent_id)
    if cached_data:
        record, timestamp = cached_data
        if (time.time() - timestamp) < CACHE_TTL_SECONDS:
            logging.info(f"Cache HIT for agent record '{agent_id}'.")
            return record
        else:
            logging.info(f"Cache STALE for agent record '{agent_id}'. Fetching...")

    # 2. If not in cache or stale, fetch from Trust Directory
    document_id = agent_id
    lookup_url = f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{document_id}"

    try:
        logging.info(f"Cache MISS. Fetching agent record for '{agent_id}' from: {lookup_url}")
        response = requests.get(lookup_url, timeout=3)  # 3 second timeout

        if response.status_code != 200:
            logging.error(f"Agent record lookup failed: Trust Directory returned {response.status_code} for {agent_id}")
            return None

        data = response.json()

        # --- P-4: New Status Check (Annexe A compliance) ---
        agent_status = data.get("status")
        if agent_status != "active":
            logging.warning(
                f"Agent record lookup failed: Agent '{agent_id}' is not active (status: {agent_status}).")
            return None  # Reject if not active
        # --- End P-4 Check ---

        # 4. Store in cache and return
        AGENT_RECORD_CACHE[agent_id] = (data, time.time())
        logging.info(f"Successfully fetched and cached agent record for: {agent_id}")
        return data

    except requests.exceptions.RequestException as e:
        logging.error(f"Agent record lookup failed: Could not connect to Trust Directory at {lookup_url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Agent record lookup failed: Error parsing record for {agent_id}: {e}")
        return None


def get_public_key(agent_id: str) -> Optional[ed25519.Ed25519PublicKey]:
    """
    (P-4 Updated) Fetches the public key for a given agent_id (now a UUID).
    Relies on get_agent_record() to handle caching and validation.
    """

    # 1. Check public key cache first (fastest)
    cached_key = PUBLIC_KEY_CACHE.get(agent_id)
    if cached_key:
        key, timestamp = cached_key
        if (time.time() - timestamp) < CACHE_TTL_SECONDS:
            logging.info(f"Cache HIT for public key '{agent_id}'.")
            return key

    # 2. If key not cached, get the full agent record
    #    This will use its own cache (AGENT_RECORD_CACHE)
    agent_record = get_agent_record(agent_id)

    if not agent_record:
        # get_agent_record() already logged the error
        return None

    # 3. Extract, load, and cache the public key
    try:
        public_key_pem = agent_record.get("public_key")
        if not public_key_pem:
            logging.error(f"Signature verification failed: Agent record for '{agent_id}' missing 'public_key'.")
            return None

        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))

        # 4. Store in *public key* cache and return
        PUBLIC_KEY_CACHE[agent_id] = (public_key, time.time())
        logging.info(f"Successfully loaded and cached public key for: {agent_id}")
        return public_key

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


# --- P-3 / P-6: New Endpoint for A2A Negotiation (EXTERNAL ROUTING) ---

@app.route("/v1/a2a/transact", methods=["POST"])
@require_api_key  # L1 Security (API Key)
def a2a_transact():
    """
    (P-6.3) Handles A2A transactions by routing to external APIs.
    This is the core routing logic of the ATP.
    """

    # --- 1. VALIDATE CONSUMER (Agent A) ---
    try:
        body = request.json  # This is the TransactionRequest
        signature_b64 = request.headers.get('X-Agent-Signature')
        consumer_agent_id = body.get("consumer_agent_id")
    except Exception as e:
        logging.error(f"Malformed A2A request: {e}")
        return jsonify({"error": "Malformed request."}), 400

    if not all([body, signature_b64, consumer_agent_id]):
        return jsonify({"error": "Malformed A2A request (missing body, signature, or consumer_agent_id)."}), 400

    # L2 Validation of Agent A
    public_key_consumer = get_public_key(consumer_agent_id)
    if not public_key_consumer:
        logging.warning(f"A2A Violation: Could not validate Consumer Agent '{consumer_agent_id}'.")
        return jsonify({"error": f"Failed to verify agent identity: {consumer_agent_id}"}), 403

    try:
        canonical_message = json.dumps(body, sort_keys=True).encode('utf-8')
        signature_bytes = base64.b64decode(signature_b64)
        public_key_consumer.verify(signature_bytes, canonical_message)
        logging.info(f"SUCCESS (A2A): Signature for Consumer Agent '{consumer_agent_id}' VERIFIED.")
    except InvalidSignature:
        logging.critical(f"FATAL: A2A VIOLATION! Invalid signature for Consumer Agent '{consumer_agent_id}'.")
        return jsonify({"error": "Invalid signature."}), 401
    except Exception as e:
        logging.error(f"Error during A2A signature verification: {e}", exc_info=True)
        return jsonify({"error": "A critical error occurred during signature verification."}), 500

    # --- 2. LOOKUP SERVICE (P-5.1) ---
    service_id = body.get("service_id")
    if not service_id:
        return jsonify({"error": "TransactionRequest missing 'service_id'."}), 400

    service_lookup_url = f"{TRUST_DIRECTORY_URL}/api/v1/services/{service_id}"
    logging.info(f"A2A Routing: Looking up service '{service_id}' at {service_lookup_url}...")

    try:
        service_response = requests.get(service_lookup_url, timeout=3)
        if service_response.status_code != 200:
            logging.error(f"A2A Routing Error: Service '{service_id}' not found (404) or Directory error.")
            return jsonify({"error": f"Service not found or invalid: {service_id}"}), 404

        service_contract = service_response.json()
        logging.info(f"A2A Routing: Found service '{service_contract.get('service_type')}'")

    except requests.exceptions.RequestException as e:
        logging.error(f"A2A Routing Error: Could not connect to Trust Directory (Service Lookup): {e}")
        return jsonify({"error": "Internal error: Failed to contact Trust Directory"}), 500

    # --- 3. IDENTIFY PROVIDER (P-5.2) ---
    provider_agent_id = service_contract.get("provider_agent_id")
    if not provider_agent_id:
        logging.error(f"A2A Routing Error: Service '{service_id}' has no 'provider_agent_id'.")
        return jsonify({"error": "Service is misconfigured (missing provider)"}), 500

    logging.info(f"A2A Routing: Identifying provider '{provider_agent_id}'...")
    provider_record = get_agent_record(provider_agent_id)  # Uses our P-4 cache

    if not provider_record:
        logging.error(f"A2A Routing Error: Could not get record for Provider Agent '{provider_agent_id}'.")
        return jsonify({"error": f"Provider agent not found or inactive: {provider_agent_id}"}), 404

    provider_endpoint = provider_record.get("metadata", {}).get("api_endpoint")
    if not provider_endpoint:
        logging.error(f"A2A Routing Error: Provider Agent '{provider_agent_id}' has no 'api_endpoint' in metadata.")
        return jsonify({"error": "Provider agent is misconfigured (missing endpoint)"}), 500

    # --- 4. NEW P-6.3 LOGIC: EXTERNAL ROUTING ---
    logging.info(f"A2A Routing (P-6): Provider is external API at {provider_endpoint}")

    # 4a. Get the path template from the service contract
    service_metadata = service_contract.get("metadata", {})
    path_template = service_metadata.get("service_path_template")
    if not path_template:
        logging.error(f"A2A Routing Error (P-6): Service '{service_id}' is missing 'metadata.service_path_template'.")
        return jsonify({"error": "Service is misconfigured (missing path template)"}), 500

    # 4b. Get the payload from Agent A's request
    payload = body.get("payload", {})

    try:
        # 4c. Build the final URL by replacing placeholders
        # (e.g., /products/{product_id} + {"product_id": "1"} -> /products/1)
        # Note: We assume all required keys exist in the payload
        final_path = path_template.format(**payload)
        final_url = f"{provider_endpoint}{final_path}"

        logging.info(f"A2A Routing (P-6): Executing GET on final URL: {final_url}")

        # 4d. Execute the external GET request
        # Note: FakeStoreAPI does not require auth headers
        provider_response = requests.get(final_url, timeout=10)
        provider_response.raise_for_status()  # Raise an exception for 4xx/5xx errors

        # 4e. Get the JSON response from the external API
        external_json_result = provider_response.json()

    except requests.exceptions.RequestException as e:
        logging.error(f"A2A Routing Error (P-6): Failed to connect to Provider API at {final_url}: {e}")
        return jsonify({"error": "Provider agent is offline or unreachable."}), 503
    except KeyError as e:
        # This happens if the payload is missing a key (e.g., 'product_id')
        logging.error(f"A2A Routing Error (P-6): Payload mismatch for template. Missing key: {e}")
        return jsonify({"error": f"Payload is missing required field: {e}"}), 400
    except Exception as e:
        logging.error(f"A2A Routing Error (P-6): Unknown error during routing: {e}")
        return jsonify({"error": "Internal routing error."}), 500

    # 4f. Wrap the external JSON into a TransactionResponse
    final_tx_response = {
        "transaction_id": body.get("transaction_id"),
        "status": "success",
        "timestamp": datetime.now(UTC).isoformat(),
        "result": external_json_result,  # The JSON from FakeStoreAPI
        "error_message": None
    }

    logging.info(f"A2A Routing (P-6): Relaying response from external provider.")
    return jsonify(final_tx_response), 200


# --- TASK P-5.4: "SLAVE" ENDPOINT (REMOVED) ---
# The /v1/services/execute_data_analysis endpoint has been removed
# as it is replaced by the P-6 external routing.

# --- Application Startup ---
if __name__ == '__main__':
    logging.info("Flask Orchestrator (P-6 FSA Ready) initialized successfully.")
    # Note: Flask's 'run' is only for local dev.
    app.run(debug=True, port=int(os.environ.get('PORT', 8080)), host='0.0.0.0')