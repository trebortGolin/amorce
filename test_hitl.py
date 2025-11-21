import requests
import json
import uuid
from datetime import datetime, timezone
from agent_client import sign_message, AGENT_ID, AGENT_API_KEY

# URL locale
URL = "https://natp-qunhcqu4ra-uc.a.run.app/v1/a2a/transact"


def run_test(has_token=False):
    print(f"\n--- TEST: Transaction {'WITH' if has_token else 'WITHOUT'} Token ---")

    payload = {
        "intent": "transaction.commit",
        "product_id": "1"
    }

    if has_token:
        payload["human_approval_token"] = "human-sig-xyz-123"

    body = {
        "transaction_id": str(uuid.uuid4()),
        "service_id": "bf8ba5d0-9337-41e3-8d96-1c593f5665c1",
        "consumer_agent_id": AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload
    }

    # 1. Signer (L2)
    signature = sign_message(body)

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": AGENT_API_KEY,
        "X-Agent-Signature": signature
    }

    # 2. Envoyer
    try:
        resp = requests.post(URL, json=body, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")

        if has_token and resp.status_code == 200:
            print("✅ SUCCESS: Valid HITL transaction accepted.")
        elif not has_token and resp.status_code == 403:
            print("✅ SUCCESS: Invalid HITL transaction blocked.")
        else:
            print("❌ FAILURE: Unexpected outcome.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Test 1: Doit échouer (403)
    run_test(has_token=False)

    # Test 2: Doit réussir (200)
    # Note: Le succès dépend aussi de la disponibilité du service 'fake store' derrière
    run_test(has_token=True)