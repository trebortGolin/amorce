import os
from google.cloud import firestore

# Configuration (Doit correspondre à ton projet)
PROJECT_ID = "amorce-prod-rgosselin"


def audit_ledger():
    print(f"\n--- AUDIT DU GRAND LIVRE (LEDGER) ---")
    print(f"Projet GCP : {PROJECT_ID}")

    try:
        db = firestore.Client(project=PROJECT_ID)
        ledger_ref = db.collection("ledger")

        # On récupère les 5 dernières transactions
        query = ledger_ref.order_by("ingested_at", direction=firestore.Query.DESCENDING).limit(5)
        results = list(query.stream())

        if not results:
            print("❌ ALERTE : Le Ledger est vide. Le metering ne fonctionne pas.")
            return

        print(f"✅ SUCCÈS : {len(results)} transactions trouvées dans le Ledger.\n")

        for doc in results:
            data = doc.to_dict()
            print(f"📄 Transaction : {doc.id}")
            print(f"   - Status : {data.get('status')}")
            print(f"   - Service : {data.get('result', {}).get('category', 'Unknown')}")  # Adapté au fake store
            print(f"   - Timestamp : {data.get('ingested_at')}")
            print("---------------------------------------------------")

    except Exception as e:
        print(f"❌ ERREUR D'AUDIT : {e}")


if __name__ == "__main__":
    audit_ledger()