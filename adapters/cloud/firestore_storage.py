"""
Firestore Transaction Storage

Logs transactions to Google Cloud Firestore for metering and billing.
This is the storage implementation for cloud mode.
"""

import logging
from typing import Optional, Dict, Any
from google.cloud import firestore
from core.interfaces import IStorage

logger = logging.getLogger(__name__)


class FirestoreStorage(IStorage):
    """
    Firestore-based transaction storage for cloud mode.
    
    Logs all transactions to a Firestore collection for:
    - Metering and billing
    - Audit trails
    - Analytics
    """
    
    def __init__(self, project_id: str, collection_name: str = "ledger"):
        """
        Initialize Firestore storage.
        
        Args:
            project_id: Google Cloud project ID
            collection_name: Firestore collection name
        """
        try:
            self.db_client = firestore.Client(project=project_id)
            self.collection_name = collection_name
            logger.info(f"Firestore storage initialized: {project_id}/{collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            raise
    
    def log_transaction(self, tx_data: Dict[str, Any]) -> None:
        """
        Log a transaction to Firestore.
        
        Args:
            tx_data: Transaction data dictionary
        """
        try:
            transaction_id = tx_data.get("transaction_id")
            if not transaction_id:
                logger.error("Cannot log transaction without transaction_id")
                return
            
            doc_ref = self.db_client.collection(self.collection_name).document(transaction_id)
            doc_ref.set({
                **tx_data,
                "ingested_at": firestore.SERVER_TIMESTAMP
            })
            
            logger.debug(f"Transaction logged to Firestore: {transaction_id}")
        except Exception as e:
            logger.error(f"Failed to log transaction to Firestore: {e}")
            # Don't raise - logging failures shouldn't break the transaction
    
    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a transaction from Firestore.
        
        Args:
            transaction_id: The transaction identifier
            
        Returns:
            Transaction data or None if not found
        """
        try:
            doc_ref = self.db_client.collection(self.collection_name).document(transaction_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            return doc.to_dict()
        except Exception as e:
            logger.error(f"Failed to retrieve transaction from Firestore: {e}")
            return None
