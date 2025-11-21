import os
import json
import base64
import requests
import time
from uuid import uuid4
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from google.cloud import secretmanager

# --- CONFIGURATION ---
# URL de l'Orchestrateur (NATP) - À définir via export NATP_URL="..."
NATP_URL = os.environ.get("NATP_URL")
# URL de l'Annuaire (Directory) - Fixe
DIRECTORY_URL = "https://amorce-trust-api-425870997313.us-central1.run.app"

# Identité de l'Agent Client (Nous)
AGENT_ID = os.environ.get("AGENT_ID", "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "sk-atp-amorce-dev-2024")
GCP_PROJECT_ID = "amorce-prod-rgosselin"
SECRET_NAME = "atp-agent-private-key"

def get_private_key():
    """Récupère la clé privée depuis GCP pour signer la transaction."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return serialization.load_pem_private_key(response.payload.data, password=None, backend=default_backend())
    except Exception as e:
        print(f"❌ ERREUR CLÉ: Impossible de charger la clé privée: {e}")
        exit(1)

def sign_payload(payload):
    """Signe le payload JSON (L2 Security)."""
    key = get_private_key()
    canonical = json.dumps(payload, sort_keys=True).encode('utf-8')
    return base64.b64encode(key.sign(canonical)).decode('utf-8')

def run_scenario():
    print(f"\n🤖 --- DÉMARRAGE DU TEST AGENT-TO-AGENT (E2E) ---")

    if not NATP_URL:
        print("❌ ERREUR: La variable NATP_URL n'est pas définie.")
        return

    # ---------------------------------------------------------
    # ÉTAPE 1 : DÉCOUVERTE (Discovery)
    # L'agent cherche un service capable de récupérer des produits.
    # ---------------------------------------------------------
    print(f"\n🔍 1. DISCOVERY: Interrogation de l'Annuaire ({DIRECTORY_URL})...")
    try:
        # On cherche le service "product_retrieval" (celui qu'on a enregistré)
        disc_resp = requests.get(
            f"{DIRECTORY_URL}/api/v1/services/search",
            params={"service_type": "product_retrieval"},
            timeout=10
        )
        disc_resp.raise_for_status()
        services = disc_resp.json()

        if not services:
            print("❌ ÉCHEC: Aucun service 'product_retrieval' trouvé dans l'annuaire.")
            return

        target_service = services[0]
        service_id = target_service['service_id']
        print(f"✅ SUCCÈS: Service trouvé !")
        print(f"   -> Service ID : {service_id}")
        print(f"   -> Provider ID: {target_service['provider_agent_id']}")

    except Exception as e:
        print(f"❌ ERREUR RÉSEAU (Discovery): {e}")
        return

    # ---------------------------------------------------------
    # ÉTAPE 2 : TRANSACTION (Execution)
    # L'agent construit une enveloppe sécurisée et l'envoie à NATP.
    # ---------------------------------------------------------
    print(f"\nFy 2. TRANSACTION: Envoi de la demande d'achat à NATP ({NATP_URL})...")

    # Le besoin métier (Payload interne)
    business_payload = {
        "product_id": "1",
        # On ajoute l'intent et le token pour passer le HITL check si nécessaire
        "intent": "transaction.commit",
        "human_approval_token": "e2e-test-token-valid"
    }

    # L'Enveloppe NATP (Protocole)
    envelope = {
        "transaction_id": str(uuid4()),
        "service_id": service_id,
        "consumer_agent_id": AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": business_payload
    }

    # Signature Cryptographique (L2)
    try:
        print("   -> Signature de l'enveloppe (Ed25519)...")
        signature = sign_payload(envelope)
    except Exception as e:
        print(f"❌ ERREUR SIGNATURE: {e}")
        return

    headers = {
        "X-API-Key": AGENT_API_KEY,       # L1 Auth
        "X-Agent-Signature": signature,   # L2 Auth
        "Content-Type": "application/json"
    }

    # Envoi
    try:
        start_time = time.time()
        tx_resp = requests.post(f"{NATP_URL}/v1/a2a/transact", json=envelope, headers=headers, timeout=15)
        duration = time.time() - start_time

        print(f"   -> Réponse reçue en {duration:.2f}s")
        print(f"   -> Status Code: {tx_resp.status_code}")

        if tx_resp.status_code == 200:
            result_json = tx_resp.json()
            print("\n🎉 --- RÉSULTAT DE LA TRANSACTION ---")
            print(f"✅ STATUT : {result_json.get('status')}")
            print(f"🆔 TX ID  : {result_json.get('transaction_id')}")

            # Affichage du produit reçu (Fake Store)
            product = result_json.get("result", {})
            print("\n📦 MARCHANDISE RECUE (Fake Store API):")
            print(f"   - Titre : {product.get('title')}")
            print(f"   - Prix  : {product.get('price')} $")
            print(f"   - Cat.  : {product.get('category')}")

            print("\n💰 METERING:")
            print("   Cette transaction a été enregistrée dans le Ledger Firestore.")

        else:
            print("\n⚠️ ÉCHEC DE LA TRANSACTION:")
            print(f"Erreur: {tx_resp.text}")

    except Exception as e:
        print(f"❌ ERREUR RÉSEAU (Transaction): {e}")

if __name__ == "__main__":
    run_scenario()