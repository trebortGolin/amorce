"""
Local File-Based Private Key Provider

Loads private keys from PEM files on disk.
"""

import os
import logging
from typing import Optional
from core.interfaces import IKeyProvider

logger = logging.getLogger(__name__)


class LocalFileKeyProvider(IKeyProvider):
    """
    File-based private key provider for standalone mode.
    
    Loads Ed25519 private keys from local PEM files.
    """
    
    def __init__(self, key_file: str, agent_id: str):
        """
        Initialize the local key provider.
        
        Args:
            key_file: Path to the PEM file containing the private key
            agent_id: The agent ID associated with this key
        """
        self.key_file = key_file
        self.agent_id_value = agent_id
        self._private_key: Optional[bytes] = None
        
        if not os.path.exists(key_file):
            raise FileNotFoundError(f"Private key file not found: {key_file}")
        
        logger.info(f"Loaded private key from {key_file}")
    
    def load_private_key(self) -> bytes:
        """
        Load the private key from the PEM file.
        
        Returns:
            Private key bytes
            
        Raises:
            Exception if key cannot be loaded
        """
        if self._private_key:
            return self._private_key
        
        try:
            with open(self.key_file, 'rb') as f:
                pem_data = f.read()
            
            # The amorce SDK will handle PEM parsing
            # For now, we return the raw bytes
            self._private_key = pem_data
            return self._private_key
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise
    
    def get_agent_id(self) -> str:
        """
        Get the agent ID.
        
        Returns:
            Agent identifier
        """
        return self.agent_id_value
