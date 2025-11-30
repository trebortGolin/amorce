import os
import uuid
import requests
import json
from amorce import IdentityManager, GoogleSecretManagerProvider

# --- Configuration ---
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "amorce-prod-rgosselin")
SECRET_NAME = os.environ.get("SECRET_NAME", "atp-agent-private-key")
DIRECTORY_URL = os.environ.get("TRUST_DIRECTORY_URL", "https://amorce-trust-api-425870997313.us-central1.run.app")

# L'UUID officiel de votre agent (celui des variables d'environnement)
OFFICIAL_AGENT_UUID = "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a"

# Schéma fictif pour passer la validation
CONVERSATION_SCHEMA = {
    "type": "object",
    "properties": {
        "message": {"type": "string"}
    }
}


def register_mock_service():
    print("🔐 Chargement de l'identité...")
    try:
        # 1. Identité (L2)
        provider = GoogleSecretManagerProvider(GCP_PROJECT_ID, SECRET_NAME)
        identity = IdentityManager(provider)

        service_uuid = str(uuid.uuid4())

        # 2. Le Payload "Proof Pudding" (Structure validée)
        payload = {
            "service_id": service_uuid,
            "provider_agent_id": OFFICIAL_AGENT_UUID,
            # On garde 'booking:flight' pour que votre smart_agent le trouve
            "service_type": "booking:flight",
            "description": "Test de compatibilite V0.1.6 Priority Lane (Mock Flight).",
            "pricing": {
                "type": "fixed",
                "amount": 10.0,  # On met un prix > 0 pour le réalisme
                "currency": "EUR"
            },
            "input_schema": CONVERSATION_SCHEMA,
            "output_schema": CONVERSATION_SCHEMA,
            # C'est ici que ça bloquait probablement : on utilise le format exact
            "metadata": {
                "service_path_template": "/mock/provider/flight"
            }
        }

        # 3. Signature L2 (Canonicalisation)
        canonical_bytes = identity.get_canonical_json_bytes(payload)
        signature = identity.sign_data(canonical_bytes)

        print(f"🚀 Envoi du service {service_uuid} au Directory...")

        resp = requests.post(
            f"{DIRECTORY_URL}/api/v1/services",
            data=canonical_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Agent-Signature": signature
            },
            timeout=10
        )

        if resp.status_code == 200:
            print("✅ SUCCÈS : Service enregistré avec le format 'Proof Pudding' !")
            print(json.dumps(resp.json(), indent=2))
        else:
            print(f"❌ ÉCHEC ({resp.status_code}) : {resp.text}")

    except Exception as e:
        print(f"❌ Erreur : {e}")


if __name__ == "__main__":
    register_mock_service()