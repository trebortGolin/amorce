import os
import time
import json
import base64
import requests
from uuid import uuid4
from datetime import datetime, timezone

import google.generativeai as genai
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from google.cloud import secretmanager

# --- CONFIGURATION ---
NATP_URL = os.environ.get("NATP_URL", "https://natp-425870997313.us-central1.run.app")
DIRECTORY_URL = "https://amorce-trust-api-425870997313.us-central1.run.app"
AGENT_ID = os.environ.get("AGENT_ID", "e4b0c7c8-4b9f-4b0d-8c1a-2b9d1c9a0c1a")
AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "sk-atp-amorce-dev-2024")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GCP_PROJECT_ID = "amorce-prod-rgosselin"
SECRET_NAME = "atp-agent-private-key"

# Variable globale pour stocker l'ID du service actif (trouvé par Discovery)
ACTIVE_SERVICE_ID = None

# --- MODULE SÉCURITÉ ---
_private_key = None


def get_signer():
    global _private_key
    if _private_key: return _private_key
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        _private_key = serialization.load_pem_private_key(response.payload.data, password=None,
                                                          backend=default_backend())
        return _private_key
    except Exception as e:
        print(f"❌ ERREUR AUTH: {e}")
        exit(1)


def sign_payload(payload):
    key = get_signer()
    canonical = json.dumps(payload, sort_keys=True).encode('utf-8')
    return base64.b64encode(key.sign(canonical)).decode('utf-8')


def call_natp(payload):
    """Appelle NATP en utilisant l'ID de service découvert dynamiquement."""
    if not ACTIVE_SERVICE_ID:
        return None

    envelope = {
        "transaction_id": str(uuid4()),
        "service_id": ACTIVE_SERVICE_ID,
        "consumer_agent_id": AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }

    try:
        signature = sign_payload(envelope)
        headers = {
            "X-API-Key": AGENT_API_KEY,
            "X-Agent-Signature": signature,
            "Content-Type": "application/json"
        }
        return requests.post(f"{NATP_URL}/v1/a2a/transact", json=envelope, headers=headers, timeout=10)
    except Exception as e:
        print(f"Erreur connexion NATP: {e}")
        return None


# --- FONCTION DE DÉCOUVERTE (DISCOVERY) ---
def perform_discovery():
    """Trouve le bon Service ID dans l'annuaire avant de commencer."""
    global ACTIVE_SERVICE_ID
    print("📡 [SYSTEM] Interrogation de l'Annuaire pour le service 'product_retrieval'...")
    try:
        resp = requests.get(f"{DIRECTORY_URL}/api/v1/services/search", params={"service_type": "product_retrieval"},
                            timeout=5)
        if resp.status_code == 200 and resp.json():
            service = resp.json()[0]
            ACTIVE_SERVICE_ID = service['service_id']
            print(f"✅ [SYSTEM] Service connecté : {ACTIVE_SERVICE_ID}")
            return True
        else:
            print("❌ [SYSTEM] Aucun service trouvé dans l'annuaire.")
            return False
    except Exception as e:
        print(f"❌ [SYSTEM] Erreur Annuaire : {e}")
        return False


# --- OUTILS IA ---

def search_catalog(ignored_query: str):
    """
    Récupère la liste brute des produits disponibles via NATP.
    L'IA filtrera elle-même les résultats.
    """
    print(f"\n⚡ [TOOL] Scan du catalogue via NATP...")
    products_found = []

    # On scanne les 5 premiers produits pour donner du contexte à l'IA
    for i in range(1, 6):
        resp = call_natp({"product_id": str(i)})
        if resp and resp.status_code == 200:
            p = resp.json().get("result", {})
            # On formate une fiche produit courte pour l'IA
            info = f"ID: {p.get('id')} | Nom: {p.get('title')} | Prix: {p.get('price')}$ | Desc: {p.get('description')[:50]}..."
            products_found.append(info)

    if not products_found:
        return "Erreur: Impossible de lire le catalogue (NATP erreur ou vide)."

    # On renvoie TOUT à l'IA. C'est elle qui fera le lien "sac" <-> "Backpack".
    return "\n".join(products_found)


def purchase_item(product_id: str):
    """Déclenche l'achat sécurisé HITL."""
    print(f"\n⚡ [TOOL] Initialisation achat ID {product_id}...")
    print(f"\n🔒 SÉCURITÉ BANCAIRE (HITL)")
    token = input("   >>> Entrez votre code de validation (ex: 'OK') : ")

    if not token: return "Transaction annulée par l'utilisateur."

    resp = call_natp({
        "product_id": str(product_id),
        "intent": "transaction.commit",
        "human_approval_token": token
    })

    if resp and resp.status_code == 200:
        return f"SUCCÈS : Transaction {resp.json().get('transaction_id')} confirmée."
    elif resp and resp.status_code == 403:
        return f"ÉCHEC : Refusé par le protocole de sécurité (Token invalide)."
    else:
        return "Erreur technique lors du paiement."


# --- MAIN ---
def run():
    if not perform_discovery():
        return

    genai.configure(api_key=GOOGLE_API_KEY)

    model = genai.GenerativeModel(
        # Utilisation du modèle stable flash
        model_name='gemini-flash-latest',
        tools=[search_catalog, purchase_item],
        system_instruction="""
        Tu es un assistant d'achat expert.
        1. Quand l'utilisateur cherche quelque chose, utilise 'search_catalog' (ignore l'argument query, appelle-le juste avec "all").
        2. Analyse la liste retournée pour trouver ce qui correspond à la demande (fais la traduction Français/Anglais toi-même).
        3. Propose le produit trouvé avec son prix.
        4. Si l'utilisateur veut acheter, utilise 'purchase_item'.
        """
    )

    chat = model.start_chat(enable_automatic_function_calling=True)
    print("\n💬 Assistant prêt. (Dites 'Je cherche un sac' ou 'Quitter')")

    while True:
        msg = input("\n👤 > ")
        if msg.lower() in ['quit', 'exit']: break
        try:
            res = chat.send_message(msg)
            print(f"🤖 > {res.text}")
        except Exception as e:
            print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    run()