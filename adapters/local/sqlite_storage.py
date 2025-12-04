"""
Local SQLite-Based Transaction Storage

Logs transactions to a local SQLite database for development and self-hosting.
"""

import sqlite3
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from core.interfaces import IStorage

logger = logging.getLogger(__name__)


class LocalSQLiteStorage(IStorage):
    """
    SQLite-based transaction storage for standalone mode.
    
    Creates a local database at data/transactions.db with transaction logs.
    """
    
    def __init__(self, db_path: str = "./data/transactions.db"):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    consumer_agent_id TEXT NOT NULL,
                    service_id TEXT,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    result TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_consumer_agent 
                ON transactions(consumer_agent_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON transactions(timestamp)
            ''')
            
            # Create approvals table for HITL
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT,
                    status TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    FOREIGN KEY (transaction_id) REFERENCES transactions (transaction_id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_approval_agent 
                ON approvals(agent_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_approval_status 
                ON approvals(status)
            ''')
            
            # Create payments table (Phase 3 - Dormant)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id TEXT PRIMARY KEY,
                    payment_request_id TEXT,
                    transaction_id TEXT NOT NULL,
                    payer_agent_id TEXT NOT NULL,
                    payee_agent_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    payment_method TEXT,
                    payment_token TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    authorized_at TEXT,
                    captured_at TEXT,
                    description TEXT,
                    FOREIGN KEY (transaction_id) REFERENCES transactions (transaction_id)
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_payment_transaction 
                ON payments(transaction_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_payment_status 
                ON payments(status)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"SQLite storage initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def log_transaction(self, tx_data: Dict[str, Any]) -> None:
        """
        Log a transaction to the database.
        
        Args:
            tx_data: Transaction data dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO transactions 
                (transaction_id, consumer_agent_id, service_id, status, timestamp, result)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                tx_data.get("transaction_id"),
                tx_data.get("consumer_agent_id"),
                tx_data.get("service_id"),
                tx_data.get("status", "unknown"),
                tx_data.get("timestamp", datetime.utcnow().isoformat()),
                json.dumps(tx_data.get("result", {}))
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Transaction logged: {tx_data.get('transaction_id')}")
        except Exception as e:
            logger.error(f"Failed to log transaction: {e}")
            # Don't raise - logging failures shouldn't break the transaction
    
    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a transaction by ID.
        
        Args:
            transaction_id: The transaction identifier
            
        Returns:
            Transaction data or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM transactions WHERE transaction_id = ?
            ''', (transaction_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                "transaction_id": row["transaction_id"],
                "consumer_agent_id": row["consumer_agent_id"],
                "service_id": row["service_id"],
                "status": row["status"],
                "timestamp": row["timestamp"],
                "result": json.loads(row["result"]) if row["result"] else {}
            }
        except Exception as e:
            logger.error(f"Failed to retrieve transaction: {e}")
            return None
    
    def store_approval(self, approval_data: Dict[str, Any]) -> None:
        """
        Store an approval request in the database.
        
        Args:
            approval_data: Approval data dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO approvals 
                (approval_id, transaction_id, agent_id, summary, details, status, 
                 approved_by, approved_at, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                approval_data.get("approval_id"),
                approval_data.get("transaction_id"),
                approval_data.get("agent_id"),
                approval_data.get("summary"),
                json.dumps(approval_data.get("details", {})),
                approval_data.get("status", "pending"),
                approval_data.get("approved_by"),
                approval_data.get("approved_at"),
                approval_data.get("created_at"),
                approval_data.get("expires_at")
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Approval stored: {approval_data.get('approval_id')}")
        except Exception as e:
            logger.error(f"Failed to store approval: {e}")
            # Don't raise - storage failures shouldn't break the flow
    
    def get_approval(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an approval by ID.
        
        Args:
            approval_id: The approval identifier
            
        Returns:
            Approval data or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM approvals WHERE approval_id = ?
            ''', (approval_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                "approval_id": row["approval_id"],
                "transaction_id": row["transaction_id"],
                "agent_id": row["agent_id"],
                "summary": row["summary"],
                "details": json.loads(row["details"]) if row["details"] else {},
                "status": row["status"],
                "approved_by": row["approved_by"],
                "approved_at": row["approved_at"],
                "created_at": row["created_at"],
                "expires_at": row["expires_at"]
            }
        except Exception as e:
            logger.error(f"Failed to retrieve approval: {e}")
            return None
    
    # --- Payment Methods (Phase 3 - Dormant) ---
    
    def store_payment(self, payment_data: Dict[str, Any]) -> None:
        """
        Store a payment record (Phase 3 feature - dormant).
        
        Table exists but feature is not enabled yet.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO payments 
                (payment_id, payment_request_id, transaction_id, payer_agent_id, 
                 payee_agent_id, amount, currency, payment_method, payment_token,
                 status, created_at, authorized_at, captured_at, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payment_data.get("payment_id"),
                payment_data.get("payment_request_id"),
                payment_data.get("transaction_id"),
                payment_data.get("payer_agent_id"),
                payment_data.get("payee_agent_id"),
                payment_data.get("amount"),
                payment_data.get("currency", "USD"),
                payment_data.get("payment_method"),
                payment_data.get("payment_token"),
                payment_data.get("status", "pending"),
                payment_data.get("created_at"),
                payment_data.get("authorized_at"),
                payment_data.get("captured_at"),
                payment_data.get("description", "")
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Payment stored: {payment_data.get('payment_id')}")
        except Exception as e:
            logger.error(f"Failed to store payment: {e}")
    
    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a payment by ID (Phase 3 feature - dormant).
        
        Table exists but feature is not enabled yet.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM payments WHERE payment_id = ?
            ''', (payment_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return {
                "payment_id": row["payment_id"],
                "payment_request_id": row["payment_request_id"],
                "transaction_id": row["transaction_id"],
                "payer_agent_id": row["payer_agent_id"],
                "payee_agent_id": row["payee_agent_id"],
                "amount": row["amount"],
                "currency": row["currency"],
                "payment_method": row["payment_method"],
                "payment_token": row["payment_token"],
                "status": row["status"],
                "created_at": row["created_at"],
                "authorized_at": row["authorized_at"],
                "captured_at": row["captured_at"],
                "description": row["description"]
            }
        except Exception as e:
            logger.error(f"Failed to retrieve payment: {e}")
            return None
