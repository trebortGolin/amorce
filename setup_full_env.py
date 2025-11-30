import os
import uuid
import requests
import json
from amorce import IdentityManager, GoogleSecretManagerProvider

# --- CONFIGURATION ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "amorce-prod-rgosselin")
SECRET_NAME = os.environ.get("SECRET_NAME", "atp-agent-private-key")
DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL", "https://amorce-trust-api-425870997313.us-central1.run.app")

# --- LA BONNE CLÉ L1 (Corrigée) ---
ADMIN_KEY = "sk-admin-amorce-2025-secure-reset"

# L'UUID officiel de votre agent (de votre liste validée)
OFFICIAL_AGENT_UUID = "0b631b00-6668-42c1-a0af-2c8cf565d7f2"

# Schéma fictif
CONVERSATION_SCHEMA = {
    "type": "object",
    "properties": {"message": {"type": "string"}}
}


def setup_environment():
    print(f"🔧 Configuration pour l'agent {OFFICIAL_AGENT_UUID}...")

    # 1. Chargement Identité
    try:
        provider = GoogleSecretManagerProvider(GCP_PROJECT_ID, SECRET_NAME)
        identity = IdentityManager(provider)
        print("✅ Identité locale chargée.")
    except Exception as e:
        print(f"❌ Erreur critique GCP : {e}")
        return

    # 2. Enregistrement Agent (L1)
    print(f"🚀 Mise à jour de l'agent sur le Trust Directory (Clé: {ADMIN_KEY[:5]}...)...")
    reg_payload = {
        "agent_id": OFFICIAL_AGENT_UUID,
        "public_key": identity.public_key_pem,
        "algorithm": "Ed25519",
        "metadata": {"name": "Mock Supplier Agent (Final)"}
    }

    reg_resp = requests.post(
        f"{DIRECTORY_URL}/api/v1/agents",
        json=reg_payload,
        headers={"X-Admin-Key": ADMIN_KEY}
    )

    if reg_resp.status_code == 200:
        print("✅ Agent synchronisé avec succès (L1 OK).")
    else:
        print(f"❌ Échec L1 ({reg_resp.status_code}): {reg_resp.text}")
        return  # Bloquant

    # 3. Publication Service (L2)
    service_uuid = str(uuid.uuid4())

    # Payload "Proof Pudding"
    service_payload = {
        "service_id": service_uuid,
        "provider_agent_id": OFFICIAL_AGENT_UUID,
        "service_type": "booking:flight",
        "description": "Vol Mock Paris - Test E2E",
        "pricing": {"type": "fixed", "amount": 10.0, "currency": "EUR"},
        "input_schema": CONVERSATION_SCHEMA,
        "output_schema": CONVERSATION_SCHEMA,
        "metadata": {"service_path_template": "/mock/provider/flight"}
    }

    # Signature
    canonical_bytes = identity.get_canonical_json_bytes(service_payload)
    signature = identity.sign_data(canonical_bytes)

    print(f"🚀 Publication du service {service_uuid}...")
    srv_resp = requests.post(
        f"{DIRECTORY_URL}/api/v1/services",
        data=canonical_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Agent-Signature": signature
        },
        timeout=10
    )

    if srv_resp.status_code == 200:
        print(f"✅ SUCCÈS TOTAL : Service enregistré !")
    else:
        print(f"❌ ÉCHEC Service ({srv_resp.status_code}) : {srv_resp.text}")


if __name__ == "__main__":
    setup_environment()