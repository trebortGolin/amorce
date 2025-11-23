# --- ORCHESTRATOR (Nexus NATP v1.4 - System Lib) ---
# STATUS: REFACTORED (Ticket-CODE-02)
# Changes:
# - Removed raw 'cryptography' imports.
# - Now imports 'nexus' as a system library.
# - Uses IdentityManager.verify_signature() for L2.
# - Uses IdentityManager.get_canonical_json_bytes() for consistency.

import os
import logging
import requests
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Optional, Dict, Tuple

# --- External Libs ---
from google.cloud import firestore
import redis
from flask import Flask, request, jsonify, g

# --- INFRASTRUCTURE: System Library Import ---
# We no longer rely on local files for core logic.
from nexus import IdentityManager, NexusEnvelope

# --- Modules ---
# 'smart_agent' must also be refactored to use 'nexus' in the next step.
import smart_agent as agent

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

if not TRUST_DIRECTORY_URL or not AGENT_API_KEY:
    logging.warning("CRITICAL: Missing Security Env Vars (TRUST_DIRECTORY_URL or AGENT_API_KEY).")

# --- DB CONNECTIONS ---

# 1. Firestore (Metering)
try:
    db_client = firestore.Client(project="amorce-prod-rgosselin")
    logging.info("✅ Firestore (Ledger): Connected")
except Exception as e:
    logging.warning(f"⚠️ Firestore Error: {e} (Metering Disabled)")
    db_client = None

# 2. Redis (Rate Limiting)
try:
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, socket_connect_timeout=0.1)
    redis_client.ping()
    logging.info("✅ Redis (Rate Limit): Connected")
except Exception as e:
    logging.warning(f"⚠️ Redis Error: {e} (Rate Limiting Disabled - Traffic Allowed)")
    redis_client = None


# --- DECORATORS & HELPERS ---

def require_api_key(f: Callable) -> Callable:
    """
    L1 Security: API Key Validation.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AGENT_API_KEY:
            return f(*args, **kwargs)

        key = request.headers.get('X-API-Key')
        if not key or key != AGENT_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401

        g.auth_source = "Orchestrator"
        return f(*args, **kwargs)

    return decorated_function


# Cache Agent Identity: {agent_id: (pem_string, timestamp)}
PUBLIC_KEY_CACHE: Dict[str, Tuple[str, float]] = {}


def get_public_key_pem(agent_id: str) -> Optional[str]:
    """
    Fetches the Public Key (PEM) from the Trust Directory.
    Implements P-1: In-memory cache with a 5-minute TTL.
    """
    cached = PUBLIC_KEY_CACHE.get(agent_id)
    if cached and (time.time() - cached[1]) < 300:
        return cached[0]

    if not TRUST_DIRECTORY_URL:
        return None

    try:
        # P-1: Lookup in Trust Directory
        resp = requests.get(f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{agent_id}", timeout=10)

        if resp.status_code != 200:
            logging.warning(f"Trust Directory lookup failed for {agent_id}: {resp.status_code}")
            return None

        data = resp.json()
        if data.get("status") != "active":
            logging.warning(f"Agent {agent_id} is not active.")
            return None

        pem = data.get("public_key")

        # Cache the PEM string directly
        PUBLIC_KEY_CACHE[agent_id] = (pem, time.time())
        return pem

    except Exception as e:
        logging.error(f"Error fetching public key: {e}")
        return None


def check_rate_limit(agent_id: str, limit: int = 10, window: int = 60):
    """
    (FR-O4) Rate Limiting via Redis.
    Rule: Max 10 requests per minute per Agent ID.
    Fail-Open: If Redis is down, we allow the traffic.
    """
    if not redis_client:
        return

    key = f"rate_limit:{agent_id}"
    try:
        current_count = redis_client.incr(key)
        if current_count == 1:
            redis_client.expire(key, window)

        if current_count > limit:
            logging.warning(f"⛔ RATE LIMIT EXCEEDED for {agent_id}: {current_count}/{limit}")
            raise Exception(f"Rate limit exceeded ({limit} req/{window}s)")

    except redis.RedisError as e:
        logging.error(f"Redis Runtime Error: {e}")


def log_ledger(tx_data: dict):
    """
    Async logging to Firestore for metering/billing.
    """
    if not db_client:
        return
    try:
        db_client.collection("ledger").document(tx_data["transaction_id"]).set({
            **tx_data,
            "ingested_at": firestore.SERVER_TIMESTAMP
        })
        logging.info("💰 Ledger: Transaction recorded.")
    except Exception as e:
        logging.error(f"Ledger Write Error: {e}")


# --- ENDPOINTS ---

@app.route("/v1/a2a/transact", methods=["POST"])
@require_api_key
def a2a_transact():
    """
    The Core Router.
    Verifies L2 Signature using Nexus SDK and routes to Provider.
    """
    try:
        body = request.json
        sig = request.headers.get('X-Agent-Signature')
        consumer_id = body.get("consumer_agent_id")

        if not all([body, sig, consumer_id]):
            return jsonify({"error": "Bad Request: Missing body, signature, or consumer_id"}), 400

        # 1. RATE LIMITING (FR-O4)
        try:
            check_rate_limit(consumer_id)
        except Exception as e:
            return jsonify({"error": str(e)}), 429

        # 2. SECURITY (L2) - REFACTORED via SDK
        # Fetch key from directory
        consumer_pub_key_pem = get_public_key_pem(consumer_id)
        if not consumer_pub_key_pem:
            return jsonify({"error": f"Identity Verification Failed: Agent {consumer_id} unknown."}), 403

        # Canonicalize the body using the SDK's standard method
        # This ensures we hash the exact same bytes that the agent signed.
        # (This replaces the manual json.dumps logic)
        canonical_bytes = IdentityManager.get_canonical_json_bytes(body)

        # Verify Signature using SDK
        is_valid = IdentityManager.verify_signature(
            public_key_pem=consumer_pub_key_pem,
            data=canonical_bytes,
            signature_b64=sig
        )

        if not is_valid:
            logging.warning(f"⛔ Invalid Signature for agent {consumer_id}")
            return jsonify({"error": "Invalid Signature"}), 403

        # 3. ROUTING (P-6)
        srv_id = body.get("service_id")

        # Resolve Service ID -> Provider URL
        srv_resp = requests.get(f"{TRUST_DIRECTORY_URL}/api/v1/services/{srv_id}", timeout=10)
        if srv_resp.status_code != 200:
            return jsonify({"error": "Service Not Found"}), 404

        contract = srv_resp.json()
        provider_id = contract['provider_agent_id']

        # Resolve Provider -> API Endpoint
        prov_resp = requests.get(f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{provider_id}", timeout=10)
        if prov_resp.status_code != 200:
            return jsonify({"error": "Provider Not Found"}), 404

        # Execute Request against Provider
        endpoint = prov_resp.json()["metadata"]["api_endpoint"]
        # Allow formatting path with payload data (e.g. /products/{id})
        path_template = contract["metadata"]["service_path_template"]
        path = path_template.format(**body.get("payload", {}))

        logging.info(f"Routing to Provider: {endpoint}{path}")
        ext_resp = requests.get(f"{endpoint}{path}", timeout=10)

        # 4. METERING (FR-O3)
        result = {
            "transaction_id": body.get("transaction_id"),
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": ext_resp.json() if ext_resp.status_code == 200 else {"error": ext_resp.text}
        }
        log_ledger(result)

        return jsonify(result), ext_resp.status_code

    except Exception as e:
        logging.error(f"System Error in a2a_transact: {e}")
        return jsonify({"error": "Internal Orchestrator Error"}), 500


@app.route('/v1/nexus/bridge', methods=['POST'])
@require_api_key
def nexus_bridge():
    """
    Bridge endpoint for No-Code tools.
    Delegates to smart_agent logic (requires smart_agent to be refactored too).
    """
    try:
        # Pass request to the internal agent logic
        return jsonify(agent.run_bridge_transaction(
            request.json.get("service_id"),
            request.json.get("payload")
        )), 200
    except Exception as e:
        logging.error(f"Bridge Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logging.info(f"Starting Nexus Orchestrator on port {port}...")
    app.run(debug=False, host='0.0.0.0', port=port)