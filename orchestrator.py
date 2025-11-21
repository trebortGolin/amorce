# --- ORCHESTRATOR (Nexus NATP v1.3 - FINAL) ---
# STATUS: GOLD MASTER (Commercial Release)
# Features:
# - L1/L2 Security (Auth & Signature)
# - Bridge (No-Code Gateway)
# - HITL (Human Validation)
# - Metering (Firestore Ledger)
# - Rate Limiting (Redis Token Bucket) - NEW (FR-O4)

import os
import json
import logging
import requests
import base64
import time
from datetime import datetime, timezone
from uuid import uuid4
from functools import wraps
from typing import Callable, Any, Optional, Dict

# --- External Libs ---
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature
from google.cloud import firestore
import redis  # NEW
from flask import Flask, request, jsonify, g

# --- Modules ---
import smart_agent as agent

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app = Flask(__name__)

TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")
# Configuration Redis (Défaut: localhost)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

if not TRUST_DIRECTORY_URL or not AGENT_API_KEY:
    logging.warning("CRITICAL: Missing Security Env Vars.")

# --- DB CONNECTIONS ---

# 1. Firestore (Metering)
try:
    db_client = firestore.Client(project="amorce-prod-rgosselin")
    logging.info("✅ Firestore (Ledger): Connected")
except Exception as e:
    logging.warning(f"⚠️ Firestore Error: {e} (Metering Disabled)")
    db_client = None

# 2. Redis (Rate Limiting) - FR-O4
try:
    # Socket timeout court (100ms) pour ne pas ralentir l'API si Redis est down
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, socket_connect_timeout=0.1)
    redis_client.ping()  # Test connection
    logging.info("✅ Redis (Rate Limit): Connected")
except Exception as e:
    logging.warning(f"⚠️ Redis Error: {e} (Rate Limiting Disabled - Traffic Allowed)")
    redis_client = None


# --- DECORATORS & HELPERS ---

def require_api_key(f: Callable) -> Callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AGENT_API_KEY: return f(*args, **kwargs)
        key = request.headers.get('X-API-Key')
        if not key or key != AGENT_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        g.auth_source = "Orchestrator"
        return f(*args, **kwargs)

    return decorated_function


# Cache Agent Identity
PUBLIC_KEY_CACHE: Dict[str, tuple] = {}


def get_public_key(agent_id: str):
    cached = PUBLIC_KEY_CACHE.get(agent_id)
    if cached and (time.time() - cached[1]) < 300: return cached[0]

    if not TRUST_DIRECTORY_URL: return None
    try:
        resp = requests.get(f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{agent_id}", timeout=10)
        if resp.status_code != 200 or resp.json().get("status") != "active": return None
        pem = resp.json().get("public_key")
        key = serialization.load_pem_public_key(pem.encode('utf-8'))
        PUBLIC_KEY_CACHE[agent_id] = (key, time.time())
        return key
    except Exception:
        return None


# --- CORE LOGIC ---

def check_rate_limit(agent_id: str, limit: int = 10, window: int = 60):
    """
    (FR-O4) Rate Limiting via Redis.
    Rule: Max 10 requests per minute per Agent ID.
    """
    if not redis_client:
        return  # Fail Open

    key = f"rate_limit:{agent_id}"
    try:
        # Incrémente le compteur atomiquement
        current_count = redis_client.incr(key)

        # Au premier appel, on fixe l'expiration (fenêtre glissante simple)
        if current_count == 1:
            redis_client.expire(key, window)

        if current_count > limit:
            logging.warning(f"⛔ RATE LIMIT EXCEEDED for {agent_id}: {current_count}/{limit}")
            raise Exception(f"Rate limit exceeded ({limit} req/{window}s)")

    except redis.RedisError as e:
        logging.error(f"Redis Runtime Error: {e}")
        # On laisse passer si Redis plante pendant l'incr


def validate_hitl(body):
    if body.get("payload", {}).get("intent") == "transaction.commit":
        if not body.get("payload", {}).get("human_approval_token"):
            raise ValueError("HITL Violation: Token required for COMMIT.")


def log_ledger(tx_data):
    if not db_client: return
    try:
        db_client.collection("ledger").document(tx_data["transaction_id"]).set({
            **tx_data, "ingested_at": firestore.SERVER_TIMESTAMP
        })
        logging.info("💰 Ledger: Transaction recorded.")
    except Exception as e:
        logging.error(f"Ledger Write Error: {e}")


# --- ENDPOINTS ---

@app.route("/v1/a2a/transact", methods=["POST"])
@require_api_key
def a2a_transact():
    try:
        body = request.json
        sig = request.headers.get('X-Agent-Signature')
        consumer = body.get("consumer_agent_id")

        if not all([body, sig, consumer]): return jsonify({"error": "Bad Request"}), 400

        # 1. RATE LIMITING (FR-O4) - First line of defense
        try:
            check_rate_limit(consumer)
        except Exception as e:
            return jsonify({"error": str(e)}), 429  # Too Many Requests

        # 2. SECURITY (L2 & HITL)
        pub_key = get_public_key(consumer)
        if not pub_key: return jsonify({"error": "Identity Failed"}), 403

        try:
            pub_key.verify(base64.b64decode(sig), json.dumps(body, sort_keys=True).encode('utf-8'))
            validate_hitl(body)
        except (InvalidSignature, ValueError) as e:
            return jsonify({"error": str(e)}), 403

        # 3. ROUTING (P-6)
        srv_id = body.get("service_id")
        srv_resp = requests.get(f"{TRUST_DIRECTORY_URL}/api/v1/services/{srv_id}", timeout=10)
        if srv_resp.status_code != 200: return jsonify({"error": "Service Not Found"}), 404

        contract = srv_resp.json()
        prov_resp = requests.get(f"{TRUST_DIRECTORY_URL}/api/v1/lookup/{contract['provider_agent_id']}", timeout=10)
        if prov_resp.status_code != 200: return jsonify({"error": "Provider Not Found"}), 404

        # Execute
        endpoint = prov_resp.json()["metadata"]["api_endpoint"]
        path = contract["metadata"]["service_path_template"].format(**body.get("payload", {}))
        ext_resp = requests.get(f"{endpoint}{path}", timeout=10)

        # 4. METERING (FR-O3)
        result = {
            "transaction_id": body.get("transaction_id"),
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": ext_resp.json()
        }
        log_ledger(result)

        return jsonify(result), 200

    except Exception as e:
        logging.error(f"System Error: {e}")
        return jsonify({"error": "Internal Error"}), 500


@app.route('/v1/nexus/bridge', methods=['POST'])
@require_api_key
def nexus_bridge():
    # Bridge uses managed identity, so we Rate Limit based on Service ID or Global
    # For V1, simple pass-through
    try:
        return jsonify(agent.run_bridge_transaction(request.json.get("service_id"), request.json.get("payload"))), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))