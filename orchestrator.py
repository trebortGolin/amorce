# --- Amorce Agent Orchestrator (Transport Layer) ---
# This file handles the Flask API, security (API Key),
# and task signature verification (Zero-Trust).
#
# PHASE 3 FIX (T-3.18):
# This version now IMPORTS and USES the real AgentClient,
# removing the internal AgentClientSimulator.

import os
import json
import logging
from functools import wraps
from pathlib import Path
from typing import Callable, Any, Optional

from flask import Flask, request, jsonify

# --- CRITICAL FIX (T-3.18) ---
# We are now importing the REAL "Brain" from the other file.
from agent_client import AgentClient

# -----------------------------

# --- Global Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Validation ---
# The Orchestrator (Transport) only needs to know the AGENT_API_KEY.
# The AGENT_CLIENT (Brain) will load its own keys (GEMINI_API_KEY, AGENT_PRIVATE_KEY).
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")
if not AGENT_API_KEY:
    logging.warning("WARNING: AGENT_API_KEY environment variable not set. API will be insecure.")
    # In a real scenario, you might raise an error:
    # raise EnvironmentError("AGENT_API_KEY must be set.")


# --- Manifest Loading ---
def load_agent_manifest() -> dict:
    """
    Loads the agent's public contract (manifest) from the JSON file.
    This uses pathlib for robust path handling.
    """
    try:
        # Use Path(__file__) to find the manifest in the same directory
        manifest_path = Path(__file__).parent / "agent-manifest.json"
        with manifest_path.open('r', encoding='utf-8') as f:
            manifest_data = json.load(f)

        # Log success and the (new) Agent ID
        logging.info(f"Manifest loaded successfully. Agent ID: {manifest_data.get('agent_id')}")
        return manifest_data

    except FileNotFoundError:
        logging.error("FATAL: agent-manifest.json not found.")
        raise
    except json.JSONDecodeError:
        logging.error("FATAL: agent-manifest.json is not valid JSON.")
        raise
    except Exception as e:
        logging.error(f"FATAL: An unexpected error occurred loading manifest: {e}")
        raise


# --- Security Decorators (API Key Auth) ---

def require_api_key(f: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to enforce API Key authentication.
    Compares the key from 'X-ATP-Key' header with the env variable.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow missing key if AGENT_API_KEY is not set (for local dev/testing)
        if not AGENT_API_KEY:
            logging.warning("API key check skipped (AGENT_API_KEY not set).")
            return f(*args, **kwargs)

        key = request.headers.get('X-ATP-Key')
        if not key or key != AGENT_API_KEY:
            logging.warning(f"Unauthorized: Invalid API Key received from {request.remote_addr}.")
            return jsonify({"error": "Unauthorized"}), 401

        return f(*args, **kwargs)

    return decorated_function


# --- Flask App Initialization ---

app = Flask(__name__)

# Load the manifest globally on startup
AGENT_MANIFEST = load_agent_manifest()

# --- CRITICAL FIX (T-3.18) ---
# Initialize the REAL AgentClient (the "Brain")
# This line is now CRITICAL. When the app starts, this __init__
# will run, which triggers the _register_with_trust_directory() call.
try:
    AGENT_CLIENT = AgentClient()
    logging.info("Flask Application and REAL Agent Client initialized.")
except Exception as e:
    logging.critical(f"Failed to initialize AgentClient: {e}")
    # We must stop the app if the client fails to init (e.g., missing keys)
    raise


# --- API Endpoints ---

@app.route('/manifest', methods=['GET'])
@require_api_key
def get_manifest():
    """
    Serves the agent's public manifest (agent-manifest.json).
    This allows orchestrators to discover capabilities and trust info.
    """
    return jsonify(AGENT_MANIFEST)


@app.route('/chat_turn', methods=['POST'])
@require_api_key
def handle_chat_turn():
    """
    The main conversational endpoint.
    It receives user input and state, passes it to the "Brain"
    (AgentClient), and returns the "Brain's" signed response.
    """
    try:
        data = request.json
        if not data or 'user_input' not in data:
            return jsonify({"error": "Invalid request: 'user_input' is required."}), 400

        user_input = data.get('user_input')
        conversation_state = data.get('conversation_state', {})

        # Pass the request to the REAL AgentClient
        response_data = AGENT_CLIENT.process_chat_turn(user_input, conversation_state)

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error in /chat_turn: {e}", exc_info=True)
        return jsonify({"error": "Internal Server Error"}), 500


# --- Application Runner ---
if __name__ == '__main__':
    # This block is for local development (e.g., `python orchestrator.py`)
    # It is NOT used by the Dockerfile's `flask run` command.
    logging.info("Running in local development mode...")
    app.run(host='0.0.0.0', port=5000)

