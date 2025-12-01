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
