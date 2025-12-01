"""
Amorce Core - Abstract Interfaces

This module defines the pluggable interfaces for the Amorce runtime.
These interfaces allow the orchestrator to run in standalone mode (local files)
or cloud mode (Amorce Directory) without changing core logic.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class IAgentRegistry(ABC):
    """
    Interface for agent discovery and public key lookup.
    
    Implementations:
    - LocalFileRegistry: Reads from config/agents.json
    - CloudDirectoryRegistry: Queries Amorce Trust Directory API
    """
    
    @abstractmethod
    def find_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Find an agent by ID.
        
        Args:
            agent_id: The unique agent identifier
            
        Returns:
            Agent metadata including:
            - agent_id: str
            - public_key: str (PEM format)
            - metadata: dict with name, api_endpoint, status
            
            Returns None if agent not found or inactive.
        """
        pass
    
    @abstractmethod
    def find_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a service contract by ID.
        
        Args:
            service_id: The unique service identifier
            
        Returns:
            Service contract including:
            - service_id: str
            - provider_agent_id: str
            - metadata: dict with name, service_path_template
            
            Returns None if service not found.
        """
        pass
    
    @abstractmethod
    def list_agents(self) -> list[Dict[str, Any]]:
        """
        List all registered agents.
        
        Returns:
            List of agent metadata dictionaries.
        """
        pass


class IStorage(ABC):
    """
    Interface for transaction logging and metering.
    
    Implementations:
    - LocalSQLiteStorage: Logs to local SQLite database
    - FirestoreStorage: Logs to Google Cloud Firestore
    """
    
    @abstractmethod
    def log_transaction(self, tx_data: Dict[str, Any]) -> None:
        """
        Log a transaction for metering/auditing.
        
        Args:
            tx_data: Transaction data including:
                - transaction_id: str
                - consumer_agent_id: str
                - service_id: str
                - status: str (success|failed)
                - timestamp: str (ISO 8601)
                - result: dict
        """
        pass
    
    @abstractmethod
    def get_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a transaction by ID.
        
        Args:
            transaction_id: The transaction identifier
            
        Returns:
            Transaction data or None if not found.
        """
        pass


class IRateLimiter(ABC):
    """
    Interface for rate limiting.
    
    Implementations:
    - NoOpRateLimiter: No rate limiting (local dev)
    - RedisRateLimiter: Redis-backed rate limiting (production)
    """
    
    @abstractmethod
    def check_limit(self, agent_id: str, limit: int = 10, window: int = 60) -> bool:
        """
        Check if an agent is within rate limits.
        
        Args:
            agent_id: The agent identifier
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            True if within limits, False if exceeded.
            
        Raises:
            Exception if limit exceeded (for fail-fast behavior)
        """
        pass


class IKeyProvider(ABC):
    """
    Interface for private key management.
    
    Implementations:
    - LocalFileKeyProvider: Reads PEM file from disk
    - GoogleSecretKeyProvider: Fetches from GCP Secret Manager
    """
    
    @abstractmethod
    def load_private_key(self) -> bytes:
        """
        Load the agent's private key.
        
        Returns:
            Private key bytes (Ed25519 format)
            
        Raises:
            Exception if key cannot be loaded
        """
        pass
    
    @abstractmethod
    def get_agent_id(self) -> str:
        """
        Get the agent ID associated with this key.
        
        Returns:
            Agent identifier
        """
        pass
