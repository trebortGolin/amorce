"""
Amorce Orchestrator - Standalone-First Architecture

The reference implementation of the Amorce Agent Transaction Protocol (AATP).
Supports two modes:
- standalone: Uses local files, no cloud dependencies
- cloud: Connects to Amorce Trust Directory and cloud services

Set via AMORCE_MODE environment variable (defaults to standalone).
"""

import os
import logging
import requests
from datetime import datetime, timezone
from functools import wraps
from typing import Callable

from flask import Flask, request, jsonify, g

# --- AMORCE SDK ---
from amorce import IdentityManager

# --- CORE ---
from core.interfaces import IAgentRegistry, IStorage, IRateLimiter
from core.protocol import AmorceProtocol, MessageValidator

# ---import Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- MODE SELECTION ---
AMORCE_MODE = os.environ.get("AMORCE_MODE", "standalone")
logger.info(f"🚀 Starting Amorce Orchestrator in {AMORCE_MODE.upper()} mode")

# --- DEPENDENCY INJECTION ---
# Based on mode, inject appropriate implementations

registry: IAgentRegistry
storage: IStorage
limiter: IRateLimiter

if AMORCE_MODE == "cloud":
    # Cloud Mode: Amorce Trust Directory + GCP services
    from adapters.cloud.directory_registry import CloudDirectoryRegistry
    from adapters.cloud.firestore_storage import FirestoreStorage
    from adapters.cloud.redis_limiter import RedisRateLimiter
    
    # Required environment variables for cloud mode
    TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL")
    if not TRUST_DIRECTORY_URL:
        raise ValueError("Cloud mode requires TRUST_DIRECTORY_URL environment variable")
    
    # Initialize cloud adapters
    registry = CloudDirectoryRegistry(TRUST_DIRECTORY_URL)
    
    # Storage (Firestore)
    try:
        project_id = os.environ.get("GCP_PROJECT_ID", "amorce-prod-rgosselin")
        storage = FirestoreStorage(project_id)
        logger.info("✅ Firestore storage enabled")
    except Exception as e:
        logger.warning(f"⚠️ Firestore unavailable: {e}")
        # Fallback to no-op storage
        from adapters.local.sqlite_storage import LocalSQLiteStorage
        storage = LocalSQLiteStorage()
    
    # Rate Limiter (Redis)
    try:
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        limiter = RedisRateLimiter(redis_host, redis_port, fail_open=True)
        logger.info("✅ Redis rate limiter enabled")
    except Exception as e:
        logger.warning(f"⚠️ Redis unavailable: {e}")
        from adapters.local.noop_limiter import NoOpRateLimiter
        limiter = NoOpRateLimiter()

else:
    # Standalone Mode: Local files, no cloud dependencies
    from adapters.local.file_registry import LocalFileRegistry
    from adapters.local.sqlite_storage import LocalSQLiteStorage
    from adapters.local.noop_limiter import NoOpRateLimiter
    
    registry = LocalFileRegistry()
    storage = LocalSQLiteStorage()
    limiter = NoOpRateLimiter()
    
    logger.info("✅ Standalone mode: Using local files")

# --- L1 AUTHENTICATION ---
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")

def require_api_key(f: Callable) -> Callable:
    """
    L1 Security: API Key Validation.
    Optional in standalone mode, required in cloud mode.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In standalone mode, API key is optional
        if AMORCE_MODE == "standalone" and not AGENT_API_KEY:
            return f(*args, **kwargs)
        
        # In cloud mode or if API key is set, validate it
        if AGENT_API_KEY:
            key = request.headers.get('X-API-Key')
            if not key or key != AGENT_API_KEY:
                return jsonify(AmorceProtocol.create_error_response(
                    AmorceProtocol.ERROR_UNAUTHORIZED,
                    "Invalid or missing API key"
                )), 401
        
        g.auth_source = "Orchestrator"
        return f(*args, **kwargs)
    
    return decorated_function


# --- ENDPOINTS ---

@app.route("/v1/a2a/transact", methods=["POST"])
@require_api_key
def a2a_transact():
    """
    The Core Router for Agent-to-Agent Transactions.
    
    Validates L2 signatures and routes transactions to providers.
    """
    try:
        body = request.json
        
        # 1. PROTOCOL VALIDATION
        is_valid, error_msg = AmorceProtocol.validate_transaction_request(body)
        if not is_valid:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                error_msg
            )), 400
        
        consumer_id = body.get("consumer_agent_id")
        
        # 2. HEADER VALIDATION
        is_valid, error_msg = MessageValidator.validate_headers(request.headers)
        if not is_valid:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                error_msg
            )), 400
        
        sig = request.headers.get('X-Agent-Signature')
        
        # 3. RATE LIMITING
        try:
            limiter.check_limit(consumer_id)
        except Exception as e:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_RATE_LIMIT,
                str(e)
            )), 429
        
        # 4. AGENT LOOKUP (via injected registry)
        consumer_agent = registry.find_agent(consumer_id)
        if not consumer_agent:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_FORBIDDEN,
                f"Agent {consumer_id} not found or inactive"
            )), 403
        
        consumer_pub_key_pem = consumer_agent.get("public_key")
        if not consumer_pub_key_pem:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_FORBIDDEN,
                "Agent public key not available"
            )), 403
        
        # 5. SIGNATURE VERIFICATION (L2 Security)
        canonical_bytes = IdentityManager.get_canonical_json_bytes(body)
        is_valid = IdentityManager.verify_signature(
            public_key_pem=consumer_pub_key_pem,
            data=canonical_bytes,
            signature_b64=sig
        )
        
        if not is_valid:
            logger.warning(f"⛔ Invalid signature for agent {consumer_id}")
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_INVALID_SIGNATURE,
                "Signature verification failed"
            )), 403
        
        # 6. SERVICE ROUTING
        srv_id = body.get("service_id")
        
        # Lookup service contract (via injected registry)
        service_contract = registry.find_service(srv_id)
        if not service_contract:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_NOT_FOUND,
                f"Service {srv_id} not found"
            )), 404
        
        provider_id = service_contract.get("provider_agent_id")
        
        # Lookup provider agent (via injected registry)
        provider_agent = registry.find_agent(provider_id)
        if not provider_agent:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_NOT_FOUND,
                f"Provider agent {provider_id} not found"
            )), 404
        
        # Execute request against provider
        endpoint = provider_agent.get("metadata", {}).get("api_endpoint")
        path_template = service_contract.get("metadata", {}).get("service_path_template", "")
        path = path_template.format(**body.get("payload", {}))
        
        logger.info(f"Routing to Provider: {endpoint}{path}")
        
        try:
            ext_resp = requests.post(
                f"{endpoint}{path}",
                json={"data": body.get("payload", {})},
                timeout=10
            )
        except requests.RequestException as e:
            logger.error(f"Provider request failed: {e}")
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_INTERNAL,
                f"Failed to reach provider: {str(e)}"
            )), 500
        
        # 7. METERING (via injected storage)
        transaction_id = body.get("transaction_id", f"tx_{datetime.now(timezone.utc).timestamp()}")
        tx_data = {
            "transaction_id": transaction_id,
            "consumer_agent_id": consumer_id,
            "service_id": srv_id,
            "status": "success" if ext_resp.status_code == 200 else "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": ext_resp.json() if ext_resp.status_code == 200 else {"error": ext_resp.text}
        }
        storage.log_transaction(tx_data)
        
        # 8. RESPONSE
        result = ext_resp.json() if ext_resp.status_code == 200 else {"error": ext_resp.text}
        return jsonify(AmorceProtocol.create_success_response(
            transaction_id=transaction_id,
            result=result
        )), ext_resp.status_code
        
    except Exception as e:
        logger.error(f"System error in a2a_transact: {e}", exc_info=True)
        return jsonify(AmorceProtocol.create_error_response(
            AmorceProtocol.ERROR_INTERNAL,
            "Internal orchestrator error"
        )), 500


@app.route('/v1/nexus/bridge', methods=['POST'])
@require_api_key
def nexus_bridge():
    """
    Bridge endpoint for No-Code tools.
    Delegates to smart_agent logic.
    
    Note: This endpoint will be deprecated in favor of direct agent integration.
    """
    try:
        import smart_agent as agent
        
        return jsonify(agent.run_bridge_transaction(
            request.json.get("service_id"),
            request.json.get("payload")
        )), 200
    except Exception as e:
        logger.error(f"Bridge error: {e}")
        return jsonify(AmorceProtocol.create_error_response(
            AmorceProtocol.ERROR_INTERNAL,
            str(e)
        )), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "mode": AMORCE_MODE,
        "version": AmorceProtocol.VERSION
    }), 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Amorce Orchestrator starting on port {port}")
    logger.info(f"📍 Mode: {AMORCE_MODE}")
    app.run(debug=False, host='0.0.0.0', port=port)