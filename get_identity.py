import os
from cryptography.hazmat.primitives import serialization
from agent_client import _get_key_from_secret_manager, AGENT_ID


def show_identity():
    print(f"\n--- BOOTSTRAP IDENTITY FOR: {AGENT_ID} ---")
    try:
        # 1. Charger la clé privée du Secret Manager
        private_key = _get_key_from_secret_manager()

        # 2. Dériver la clé publique
        public_key = private_key.public_key()

        # 3. Formater en PEM
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        print("\nCOPIE CETTE COMMANDE CURL POUR L'ENREGISTRER :\n")

        # Nettoyage du PEM pour le JSON (une seule ligne avec \n)
        pem_json = pem.replace('\n', '\\n')

        curl_cmd = f"""curl -X POST "https://amorce-trust-api-425870997313.us-central1.run.app/api/v1/agents" \\
  -H "Content-Type: application/json" \\
  -H "X-Admin-Key: [TON_ADMIN_KEY_ICI]" \\
  -d '{{
    "agent_id": "{AGENT_ID}",
    "public_key": "{pem_json}",
    "algorithm": "Ed25519",
    "metadata": {{ "name": "Backend Smart Agent (Test)", "api_endpoint": "http://localhost:8080" }}
  }}'"""

        print(curl_cmd)
        print("\n------------------------------------------\n")

    except Exception as e:
        print(f"Erreur: {e}")


if __name__ == "__main__":
    show_identity()