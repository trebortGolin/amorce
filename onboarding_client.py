"""
Amorce Onboarding Client (P-8.3)

Ce script simule un agent tiers ("Agent C") qui s'enregistre
sur l'Annuaire de Confiance (amorce-trust-api).

Il exécute le flux d'onboarding en deux étapes :
1.  (L1) S'enregistrer : Appelle POST /api/v1/agents (avec clé Admin L1)
    pour créer son identité.
2.  (L2) Publier : Appelle POST /api/v1/services (avec signature L2)
    pour publier un nouveau service en son nom propre.
"""

import os
import requests
import json
import base64
from uuid import uuid4
from datetime import datetime, UTC

# --- Cryptography Imports (pour générer l'identité de l'Agent C) ---
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# --- Configuration ---

# 1. URL de l'Annuaire (cible)
# Doit correspondre à l'URL de notre service 'amorce-trust-api'
TRUST_DIRECTORY_URL = "https://amorce-trust-api-425870997313.us-central1.run.app"

# 2. Clé L1 (Admin)
# Requis pour l'étape 1 (Enregistrement)
# DOIT être configurée dans l'environnement
DIRECTORY_ADMIN_KEY = os.environ.get("DIRECTORY_ADMIN_KEY")


def generate_new_agent_identity():
    """
    Génère une nouvelle identité (Agent C) : ID, clé privée, clé publique.
    """
    print("--- 1. Génération de l'identité (Agent C) ---")

    # 1. Générer la clé privée Ed25519
    private_key = ed25519.Ed25519PrivateKey.generate()

    # 2. Extraire la clé publique
    public_key = private_key.public_key()

    # 3. Formater la clé publique en PEM (le format standard)
    public_key_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

    # 4. Générer un nouvel ID d'agent
    agent_id = uuid4()

    print(f"Nouvel Agent ID (Agent C): {agent_id}")
    print(f"Clé Publique (PEM):\n{public_key_pem[:100]}...")  # Affiche un aperçu

    return agent_id, private_key, public_key_pem


def sign_message(private_key, message_body: dict) -> str:
    """
    Signe un corps de message (dict) avec la clé privée fournie.
    """
    # La canonisation est critique :
    # Le JSON doit être compact (pas d'espaces) et les clés triées.
    canonical_message = json.dumps(
        message_body,
        sort_keys=True,
        separators=(',', ':')
    ).encode('utf-8')

    signature = private_key.sign(canonical_message)
    return base64.b64encode(signature).decode('utf-8')


def step_1_register_agent(agent_id: str, public_key_pem: str):
    """
    Tâche P-8.1 : Appelle l'endpoint /agents (L1) pour s'enregistrer.
    """
    print("\n--- 2. Tâche P-8.1 : Enregistrement (L1) ---")

    if not DIRECTORY_ADMIN_KEY:
        print("ERREUR: La variable d'environnement DIRECTORY_ADMIN_KEY n'est pas configurée.")
        print("L'étape 1 (enregistrement L1) ne peut pas continuer.")
        raise ValueError("DIRECTORY_ADMIN_KEY non fournie.")

    # C'est l'endpoint que nous avons sécurisé avec 'require_admin_key'
    register_url = f"{TRUST_DIRECTORY_URL}/api/v1/agents"

    # C'est le payload attendu par notre 'AgentRegistrationPayload' (main.py)
    payload = {
        "agent_id": str(agent_id),
        "public_key": public_key_pem,
        "algorithm": "Ed25519",
        "metadata": {
            "name": "Agent C (Onboarding Test)",
            "api_endpoint": "http://example.com/agent-c-api"
        }
    }

    # L'en-tête L1 (X-Admin-Key) est requis pour cette opération
    headers = {
        "X-Admin-Key": DIRECTORY_ADMIN_KEY,
        "Content-Type": "application/json"
    }

    print(f"Appel de POST {register_url} (avec clé L1)...")

    try:
        response = requests.post(register_url, json=payload, headers=headers, timeout=10)

        # Lève une exception si l'API renvoie 4xx ou 5xx
        response.raise_for_status()

        print("SUCCÈS (L1) : Enregistrement de l'Agent C réussi.")
        print(json.dumps(response.json(), indent=2))

    except requests.exceptions.RequestException as e:
        print("\n--- ÉCHEC (L1) ---")
        if e.response is not None:
            print(f"Erreur HTTP {e.response.status_code}:")
            try:
                # Tente d'afficher l'erreur JSON de l'API (ex: "Invalid Admin Key")
                print(e.response.json())
            except json.JSONDecodeError:
                print(e.response.text)
        else:
            print(f"Erreur de connexion : {e}")
        raise  # Arrête le script si l'enregistrement échoue


def step_2_publish_service(agent_id: str, private_key):
    """
    Tâche P-8.2 : Appelle l'endpoint /services (L2) pour publier un service.
    """
    print("\n--- 3. Tâche P-8.2 : Publication (L2) ---")

    # C'est l'endpoint que nous avons sécurisé avec 'verify_l2_signature'
    publish_url = f"{TRUST_DIRECTORY_URL}/api/v1/services"

    # C'est le 'ServiceContract' que nous voulons publier
    # Notez que le 'provider_agent_id' est NOTRE propre ID (Agent C)
    service_payload = {
        "service_id": str(uuid4()),
        "provider_agent_id": str(agent_id),
        "service_type": "hello_world",  # Le type que l'Agent A (smart_agent) cherchera
        "description": "Un service de test pour l'onboarding P-8.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
        "output_schema": {"type": "object", "properties": {"greeting": {"type": "string"}}},
        "pricing": {
            "type": "fixed",
            "amount": 0.0,
            "currency": "NEX"
        },
        "metadata": {
            # Note : Ce service est un "faux" service.
            # L'orchestrateur ne pourrait pas le router
            # car l'api_endpoint (http://example.com) n'est pas réel.
            "service_path_template": "/say_hello"
        }
    }

    # Tâche P-8.2 : Nous devons signer le payload avec notre clé privée
    try:
        signature = sign_message(private_key, service_payload)
        print(f"Contrat de service signé (Signature L2 : {signature[:10]}...)")
    except Exception as e:
        print(f"ERREUR: N'a pas pu signer le contrat de service : {e}")
        raise

    # L'en-tête L2 (X-Agent-Signature) est requis
    headers = {
        "X-Agent-Signature": signature,
        "Content-Type": "application/json"
    }

    print(f"Appel de POST {publish_url} (avec signature L2)...")

    try:
        response = requests.post(publish_url, json=service_payload, headers=headers, timeout=10)

        response.raise_for_status()

        print("SUCCÈS (L2) : Publication du service 'hello_world' réussie.")
        print(json.dumps(response.json(), indent=2))

    except requests.exceptions.RequestException as e:
        print("\n--- ÉCHEC (L2) ---")
        if e.response is not None:
            print(f"Erreur HTTP {e.response.status_code}:")
            try:
                # Ex: "Invalid signature" ou "Signature identity does not match..."
                print(e.response.json())
            except json.JSONDecodeError:
                print(e.response.text)
        else:
            print(f"Erreur de connexion : {e}")
        raise


# --- Exécution Principale ---
if __name__ == "__main__":
    try:
        # ÉTAPE 0 : Générer l'identité de l'Agent C
        agent_c_id, agent_c_private_key, agent_c_public_pem = generate_new_agent_identity()

        # ÉTAPE 1 (L1) : Enregistrer l'Agent C
        step_1_register_agent(agent_c_id, agent_c_public_pem)

        # ÉTAPE 2 (L2) : Publier le service de l'Agent C
        step_2_publish_service(agent_c_id, agent_c_private_key)

        print("\n--- VALIDATION P-8.3 RÉUSSIE ---")
        print("L'Agent C a été créé (L1) et a publié son service (L2).")
        print(f"ID de l'Agent C : {agent_c_id}")

    except Exception as e:
        print("\n--- ÉCHEC DU SCRIPT D'ONBOARDING ---")
        # Les erreurs spécifiques ont déjà été affichées par les fonctions
        pass