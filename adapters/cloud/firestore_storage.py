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
    
    def store_approval(self, approval_data: Dict[str, Any]) -> None:
        """
        Store an approval request in Firestore.
        
        Args:
            approval_data: Approval data dictionary
        """
        try:
            approval_id = approval_data.get("approval_id")
            if not approval_id:
                logger.error("Cannot store approval without approval_id")
                return
            
            doc_ref = self.db_client.collection("approvals").document(approval_id)
            doc_ref.set({
                **approval_data,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            
            logger.debug(f"Approval stored in Firestore: {approval_id}")
        except Exception as e:
            logger.error(f"Failed to store approval in Firestore: {e}")
            # Don't raise - storage failures shouldn't break the flow
    
    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an approval from Firestore.
        
        Args:
            approval_id: The approval identifier
            
        Returns:
            Approval data or None if not found
        """
        try:
            doc_ref = self.db_client.collection("approvals").document(approval_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            return doc.to_dict()
        except Exception as e:
            logger.error(f"Failed to retrieve approval from Firestore: {e}")
            return None
    
    # --- Payment Methods (Phase 3 - Dormant) ---
    
    def store_payment(self, payment_data: Dict[str, Any]) -> None:
        """
        Store a payment record in Firestore (Phase 3 feature - dormant).
        
        Collection exists but feature is not enabled yet.
        """
        try:
            payment_id = payment_data.get("payment_id")
            if not payment_id:
                logger.error("Cannot store payment without payment_id")
                return
            
            doc_ref = self.db_client.collection("payments").document(payment_id)
            doc_ref.set({
                **payment_data,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            
            logger.debug(f"Payment stored in Firestore: {payment_id}")
        except Exception as e:
            logger.error(f"Failed to store payment in Firestore: {e}")
    
    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a payment from Firestore (Phase 3 feature - dormant).
        
        Collection exists but feature is not enabled yet.
        """
        try:
            doc_ref = self.db_client.collection("payments").document(payment_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            return doc.to_dict()
        except Exception as e:
            logger.error(f"Failed to retrieve payment from Firestore: {e}")
            return None
