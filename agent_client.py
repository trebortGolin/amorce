import os
import json
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from google.cloud import secretmanager

# --- Configuration ---
# Ces variables sont chargées depuis l'environnement (export ...)
AGENT_ID = os.environ.get("AGENT_ID", "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY")

# Configuration GCP pour récupérer la clé privée
GCP_PROJECT_ID = "amorce-prod-rgosselin"
SECRET_NAME = "atp-agent-private-key"

# Cache pour éviter de rappeler Google Secret Manager à chaque fois
_private_key_cache = None


def _get_key_from_secret_manager():
    """
    Charge la clé privée Ed25519 depuis Google Secret Manager.
    """
    global _private_key_cache
    if _private_key_cache:
        return _private_key_cache

    try:
        # On ne log pas ici pour ne pas polluer la sortie du test
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        pem_data = response.payload.data

        _private_key_cache = serialization.load_pem_private_key(
            pem_data,
            password=None,
            backend=default_backend()
        )
        return _private_key_cache

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to load private key from Secret Manager: {e}")
        raise


def sign_message(message_body: dict) -> str:
    """
    Signe un payload JSON avec la clé privée de l'agent (L2 Security).
    Utilisé par les tests pour simuler un agent valide.
    """
    private_key = _get_key_from_secret_manager()

    # Canonicalisation (Tri des clés) obligatoire pour la vérification
    canonical_message = json.dumps(message_body, sort_keys=True).encode('utf-8')

    # Signature Ed25519
    signature = private_key.sign(canonical_message)

    # Encodage Base64 pour le header HTTP
    return base64.b64encode(signature).decode('utf-8')