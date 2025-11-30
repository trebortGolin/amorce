# --- SMART AGENT (Amorce NATP v1.4 - System Lib) ---
# STATUS: REFACTORED (Ticket-CODE-03)
# Role:
# 1. "Agent A" Logic (Gemini Brain)
# 2. Bridge Logic (Called by Orchestrator)
#
# Changes:
# - Replaced raw cryptography/requests with 'nexus' system library.
# - Implements 'AmorceClient' for all interactions.

import os
import json
import logging
import google.generativeai as genai
from typing import Dict, Any, Optional

# --- INFRASTRUCTURE: System Library Import ---
from amorce import AmorceClient, IdentityManager, GoogleSecretManagerProvider

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("smart_agent")

# Identity Configuration
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "amorce-prod-rgosselin")
SECRET_NAME = os.environ.get("SECRET_NAME", "atp-agent-private-key")
AGENT_ID = os.environ.get("AGENT_ID", "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")

logger.info(f"DEBUG: Client loaded AGENT_API_KEY (First 8 chars): {AGENT_API_KEY[:8] if AGENT_API_KEY else 'NONE/EMPTY'}")

# Network Configuration
TRUST_DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL")

# Gemini Configuration
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# --- SINGLETONS ---
_identity_manager: Optional[IdentityManager] = None
_nexus_client: Optional[AmorceClient] = None


def get_nexus_client() -> AmorceClient:
    """
    Initializes and returns a singleton AmorceClient.
    Loads identity from Google Secret Manager if not already loaded.
    """
    global _identity_manager, _nexus_client

    if _nexus_client:
        return _nexus_client

    # --- 1. LOAD IDENTITY (Partie qui manquait) ---
    if not _identity_manager:
        logger.info(f"🔐 Loading identity from Secret Manager: {SECRET_NAME}...")
        try:
            provider = GoogleSecretManagerProvider(
                project_id=GCP_PROJECT_ID,
                secret_name=SECRET_NAME
            )
            _identity_manager = IdentityManager(provider)
        except Exception as e:
            logger.critical(f"Failed to load identity: {e}")
            raise
    # ----------------------------------------------

    # 2. Initialize Client
    logger.info("🔌 Initializing Amorce Client...")
    _nexus_client = AmorceClient(
        identity=_identity_manager,
        directory_url=TRUST_DIRECTORY_URL,
        orchestrator_url=ORCHESTRATOR_URL,
        api_key=AGENT_API_KEY,
        agent_id=AGENT_ID
    )
    return _nexus_client


# --- BRIDGE FUNCTIONALITY (Called by Orchestrator) ---

def run_bridge_transaction(service_id: str, payload: dict) -> dict:
    """
    Called by the Orchestrator (Bridge Endpoint).
    Proxies a request from a No-Code tool to the ATP Network.

    Args:
        service_id: The target service UUID.
        payload: The business logic data.

    Returns:
        The full transaction result from the provider.
    """
    logger.info(f"🌉 BRIDGE: Processing request for service {service_id}")

    try:
        client = get_nexus_client()

        # Construct a minimal service contract (client.transact needs it for routing)
        # In a full implementation, we might resolve it first, but here we just need the ID.
        service_contract = {"service_id": service_id}

        # Execute Transaction via SDK
        # The SDK handles Envelope creation, Signing (L2), and Transport.
        response = client.transact(service_contract, payload)

        if response:
            return response
        else:
            return {"status": "failed", "error": "Transaction returned no response."}

    except Exception as e:
        logger.error(f"Bridge Transaction Failed: {e}")
        return {"status": "failed", "error": str(e)}


# --- AGENT A LOGIC (Standalone Gemini Loop) ---

def run_agent_loop():
    """
    Main loop for the Autonomous Agent (Agent A).
    Negotiates with a supplier using Gemini.
    """
    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY not set. Cannot start Brain.")
        return

    client = get_nexus_client()

    # 1. Discover Service
    logger.info("🔍 Discovering 'flight' services...")
    services = client.discover("booking:flight")

    if not services:
        logger.warning("No services found.")
        return

    target_service = services[0]
    logger.info(f"🎯 Target Service Found: {target_service.get('metadata', {}).get('name')}")

    # 2. Initialize Gemini
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

    chat = model.start_chat(history=[
        {"role": "user", "parts": "You are a buyer agent. You want a flight to Paris. Budget: 600 EUR."}
    ])

    # 3. Negotiation Loop (Simplified)
    # Ideally, this would loop based on Gemini's output.
    # For this refactor, we demonstrate a single secure transaction.

    user_intent = {
        "intent": "negotiation.start",
        "parameters": {
            "destination": "CDG",
            "date": "2025-10-12",
            "budget": 600
        }
    }

    logger.info("🚀 Sending secure transaction...")
    result = client.transact(target_service, user_intent)

    logger.info(f"✅ Transaction Result: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    # If run directly, execute the Agent Loop
    run_agent_loop()