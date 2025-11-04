"""
Orchestrator (Transport Layer) - Amorce Project (v3.3 - Phase 4)

This file manages the Flask API, which serves as the "Transport Layer" for the agent.
It handles two primary responsibilities:
1.  Authentication (via API Key) using the @require_api_key decorator.
2.  Signature Verification (Phase 4): It intercepts the 'signed_task' from the 
    AgentClient, fetches the agent's public key from the Trust Directory,
    and cryptographically verifies the signature *before* sending the
    response to the end-user.
"""

import os
import json
import logging
import requests  # <-- PHASE 4 IMPORT
import base64    # <-- PHASE 4 IMPORT
from functools import wraps
from pathlib import Path
from typing import Callable, Any, Optional, Dict

# --- PHASE 4: Cryptography Imports for Verification ---
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

from flask import Flask, request, jsonify

# --- PHASE 3: Import the *real* AgentClient ---
# This ensures we are not using the old simulator.
from agent_client import AgentClient

# --- Global Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

# Load the single API key from the environment
API_KEY = os.environ.get("AGENT_API_KEY")
if not API_KEY:
    logging.warning("AGENT_API_KEY environment variable not set. API will be insecure.")

# --- PHASE 4: Load the Trust Directory URL ---
# The orchestrator needs this to *look up* public keys for verification.
TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL")
if not TRUST_DIRECTORY_URL:
    logging.warning("TRUST_DIRECTORY_URL not set. Signature verification will fail.")

# --- Authentication Decorator (Security Layer 1) ---
def require_api_key(f: Callable) -> Callable:
    """
    Decorator to ensure the 'X-ATP-Key' header is present and valid.
    This is the first line of defense.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not API_KEY:
            # If no API_KEY is set on the server, bypass auth (insecure mode)
            logging.warning("Bypassing API key check (server key not set).")
            return f(*args, **kwargs)

        key = request.headers.get('X-ATP-Key')
        if not key or key != API_KEY:
            logging.warning(f"Unauthorized access attempt. Invalid API Key provided.")
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)
    return decorated_function

# --- Signature Verification Decorator (Security Layer 2 - PHASE 4) ---

# A simple in-memory cache for public keys
# { "agent_id": Ed25519PublicKey, ... }
PUBLIC_KEY_CACHE: Dict[str, ed25519.Ed25519PublicKey] = {}

def get_public_key(agent_id: str) -> Optional[ed25519.Ed25519PublicKey]:
    """
    Fetches the public key for a given agent_id from the Trust Directory.
    Implements a simple in-memory cache.
    """
    if not TRUST_DIRECTORY_URL:
        logging.error("FATAL: TRUST_DIRECTORY_URL is not set. Cannot verify signatures.")
        return None

    # 1. Check cache first
    if agent_id in PUBLIC_KEY_CACHE:
        return PUBLIC_KEY_CACHE[agent_id]

    # 2. If not in cache, fetch from Trust Directory
    try:
        # Sanitize the agent_id to match the document_id format (amorce.io/default -> amorce.io_default)
        document_id = agent_id.replace("/", "_")
        lookup_url = f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{document_id}"

        logging.info(f"Cache miss. Fetching public key for '{agent_id}' from: {lookup_url}")
        response = requests.get(lookup_url, timeout=3)

        if response.status_code != 200:
            logging.error(f"Signature verification failed: Agent ID '{agent_id}' not found in Trust Directory (Status {response.status_code}).")
            return None

        data = response.json()
        public_key_pem = data.get("public_key")

        if not public_key_pem:
            logging.error(f"Signature verification failed: Trust Directory response for '{agent_id}' missing 'public_key'.")
            return None

        # 3. Load the PEM string into a cryptography object
        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))

        # 4. Store in cache and return
        PUBLIC_KEY_CACHE[agent_id] = public_key
        logging.info(f"Successfully fetched and cached public key for: {agent_id}")
        return public_key

    except requests.exceptions.RequestException as e:
        logging.error(f"Signature verification failed: Could not connect to Trust Directory at {lookup_url}: {e}")
        return None
    except Exception as e:
        logging.error(f"Signature verification failed: Error parsing public key for {agent_id}: {e}")
        return None

def verify_task_signature(f: Callable) -> Callable:
    """
    Decorator to verify the 'signed_task' from the agent client
    before forwarding it in the response.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # --- 1. Get the response from the main route (e.g., process_chat_turn) ---
        # This response contains the signed_task generated by our *own* agent_client
        response_data, status_code = f(*args, **kwargs)

        # Bypass verification if the response is an error (e.g., 400 Bad Request)
        if status_code != 200:
            return response_data, status_code

        signed_task = response_data.get("signed_task")
        if not signed_task:
            logging.error("Zero-Trust Violation: Agent did not produce a 'signed_task' wrapper.")
            return jsonify({"error": "Agent failed to produce a signed task."}), 500

        # --- 2. Extract components ---
        task = signed_task.get("task")
        signature_b64 = signed_task.get("signature")
        agent_id = task.get("agent_id") if task else None

        if not all([task, signature_b64, agent_id]):
            logging.error("Zero-Trust Violation: Signed task is missing 'task', 'signature', or 'agent_id'.")
            return jsonify({"error": "Malformed signed task from agent."}), 500

        # --- 3. Get Public Key from Trust Directory ---
        public_key = get_public_key(agent_id)
        if not public_key:
            logging.error(f"Zero-Trust Violation: Could not retrieve public key for agent '{agent_id}'.")
            return jsonify({"error": f"Failed to verify agent identity: {agent_id}"}), 403 # 403 Forbidden

        # --- 4. Verify Signature ---
        try:
            # 4a. Canonicalize the task data (must match *exactly* how the agent signed it)
            canonical_task = json.dumps(task, sort_keys=True, separators=(',', ':'))
            task_bytes = canonical_task.encode('utf-8')

            # 4b. Decode the signature from Base64
            signature_bytes = base64.b64decode(signature_b64)

            # 4c. Verify!
            public_key.verify(signature_bytes, task_bytes)

            logging.info(f"SUCCESS: Signature for agent '{agent_id}' VERIFIED.")

            # --- 5. Return the original (verified) response ---
            return response_data, 200

        except InvalidSignature:
            logging.critical(f"FATAL: ZERO-TRUST VIOLATION! Invalid signature for agent '{agent_id}'. Task is compromised.")
            return jsonify({"error": f"FATAL: Invalid signature from agent '{agent_id}'."}), 403 # 403 Forbidden
        except Exception as e:
            logging.error(f"Error during signature verification: {e}", exc_info=True)
            return jsonify({"error": "A critical error occurred during signature verification."}), 500

    return decorated_function

# --- API Endpoints ---

@app.route("/manifest", methods=["GET"])
@require_api_key
def get_manifest():
    """
    Serves the 'agent-manifest.json' file.
    This is the public "business card" for the agent.
    """
    return jsonify(AGENT_MANIFEST)

@app.route("/chat_turn", methods=["POST"])
@require_api_key
@verify_task_signature  # <-- PHASE 4: Apply the verification decorator
def chat_turn():
    """
    Handles the primary conversational turn.
    1. Receives user input.
    2. Passes it to the AgentClient (The Brain).
    3. The Brain processes it and returns a 'signed_task'.
    4. @verify_task_signature intercepts and verifies the signature.
    5. The verified response is sent to the user.
    """
    data = request.json
    if not data or "user_input" not in data or "conversation_state" not in data:
        return jsonify({"error": "Missing 'user_input' or 'conversation_state'."}), 400

    try:
        # Pass the data to the *real* agent client
        response = AGENT_CLIENT.process_chat_turn(
            user_input=data["user_input"],
            conversation_state=data["conversation_state"]
        )
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"An error occurred during chat_turn processing: {e}", exc_info=True)
        return jsonify({"error": "Internal server error."}), 500

# --- Initialization ---

def load_agent_manifest() -> dict:
    """
    Loads the agent-manifest.json file from disk.
    (Phase 2: Simplified to just load the file)
    """
    try:
        manifest_path = Path(__file__).parent / "agent-manifest.json"
        with manifest_path.open('r', encoding='utf-8') as f:
            manifest_data = json.load(f)
            logging.info(f"Manifest loaded successfully. Agent ID: {manifest_data.get('agent_id')}")
            return manifest_data
    except FileNotFoundError:
        logging.critical("FATAL: 'agent-manifest.json' not found.")
        raise
    except json.JSONDecodeError:
        logging.critical("FATAL: 'agent-manifest.json' is not valid JSON.")
        raise
    except Exception as e:
        logging.critical(f"An unknown error occurred loading manifest: {e}")
        raise

# --- Application Startup ---
if __name__ == '__main__':
    # Load the manifest once on startup
    AGENT_MANIFEST = load_agent_manifest()

    # Initialize the Agent Client (The Brain) once on startup
    # This call will trigger the Trust Directory registration.
    try:
        AGENT_CLIENT = AgentClient()
    except EnvironmentError as e:
        logging.critical(f"Failed to initialize AgentClient: {e}")
        # We exit if the client fails to init (e.g., missing keys)
        exit(1)

    logging.info("Flask Application and Agent Client initialized successfully.")
    # Note: Flask's 'run' is only for local dev.
    # Gunicorn or a PaaS (like Cloud Run) is used in production.
    app.run(debug=True, port=int(os.environ.get('PORT', 8080)), host='0.0.0.0')
else:
    # This block runs when Gunicorn or Cloud Run loads the file.
    AGENT_MANIFEST = load_agent_manifest()
    try:
        AGENT_CLIENT = AgentClient()
    except EnvironmentError as e:
        logging.critical(f"Failed to initialize AgentClient: {e}")
        exit(1)
    logging.info("Flask Application (Production) and Agent Client initialized successfully.")