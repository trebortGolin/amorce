import os
import requests
import logging
from nexus import GoogleSecretManagerProvider, IdentityManager

# Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_identity")

AGENT_ID = os.environ.get("AGENT_ID")
# Utilise la clé Admin L1 que tu as utilisée pour le déploiement initial
DIRECTORY_ADMIN_KEY = os.environ.get("DIRECTORY_ADMIN_KEY")
TRUST_DIRECTORY_URL = "https://amorce-trust-api-425870997313.us-central1.run.app"
GCP_PROJECT_ID = "amorce-prod-rgosselin"
SECRET_NAME = "atp-agent-private-key"


def main():
    if not AGENT_ID or not DIRECTORY_ADMIN_KEY:
        logger.error("Please set AGENT_ID and DIRECTORY_ADMIN_KEY environment variables.")
        return

    try:
        # 1. Get the TRUE public key from Secret Manager
        logger.info("Loading private key from Secret Manager...")
        provider = GoogleSecretManagerProvider(project_id=GCP_PROJECT_ID, secret_name=SECRET_NAME)
        identity = IdentityManager(provider)
        public_key = identity.public_key_pem
        logger.info("Public Key retrieved successfully.")

        # 2. Update the Directory
        url = f"{TRUST_DIRECTORY_URL}/api/v1/agents"
        payload = {
            "agent_id": AGENT_ID,
            "public_key": public_key,
            "algorithm": "Ed25519",
            "metadata": {
                "name": "Agent A (Fixed Identity)",
                "api_endpoint": "https://client-agent-service-425870997313.us-central1.run.app"
            }
        }
        headers = {
            "X-Admin-Key": DIRECTORY_ADMIN_KEY,
            "Content-Type": "application/json"
        }

        logger.info(f"Updating Directory for Agent {AGENT_ID}...")
        resp = requests.post(url, json=payload, headers=headers)

        if resp.status_code == 200:
            logger.info("SUCCESS: Identity synchronized! KEY-MISMATCH should be gone.")
        else:
            logger.error(f"FAILED: {resp.status_code} - {resp.text}")

    except Exception as e:
        logger.error(f"Crash: {e}")


if __name__ == "__main__":
    main()