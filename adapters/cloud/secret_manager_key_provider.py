"""
Google Secret Manager Key Provider

Fetches private keys from Google Cloud Secret Manager.
This is the key provider for cloud mode.
"""

import logging
from core.interfaces import IKeyProvider
from amorce import GoogleSecretManagerProvider, IdentityManager

logger = logging.getLogger(__name__)


class GoogleSecretKeyProvider(IKeyProvider):
    """
    Google Secret Manager-based key provider for cloud mode.
    
    Fetches Ed25519 private keys from GCP Secret Manager.
    Uses the amorce SDK's built-in GoogleSecretManagerProvider.
    """
    
    def __init__(self, project_id: str, secret_name: str, agent_id: str):
        """
        Initialize the Google Secret Manager key provider.
        
        Args:
            project_id: Google Cloud project ID
            secret_name: Secret Manager secret name
            agent_id: The agent ID associated with this key
        """
        self.project_id = project_id
        self.secret_name = secret_name
        self.agent_id_value = agent_id
        self._identity_manager: IdentityManager = None
        
        logger.info(f"Loading identity from Secret Manager: {secret_name}")
        
        try:
            provider = GoogleSecretManagerProvider(
                project_id=project_id,
                secret_name=secret_name
            )
            self._identity_manager = IdentityManager(provider)
            logger.info("Identity loaded successfully from Secret Manager")
        except Exception as e:
            logger.error(f"Failed to load identity from Secret Manager: {e}")
            raise
    
    def load_private_key(self) -> bytes:
        """
        Load the private key from Secret Manager.
        
        Returns:
            Private key bytes
            
        Raises:
            Exception if key cannot be loaded
        """
        if not self._identity_manager:
            raise Exception("Identity manager not initialized")
        
        # The IdentityManager handles the key internally
        # We return the raw private key bytes for compatibility
        return self._identity_manager.private_key
    
    def get_agent_id(self) -> str:
        """
        Get the agent ID.
        
        Returns:
            Agent identifier
        """
        return self.agent_id_value
    
    def get_identity_manager(self) -> IdentityManager:
        """
        Get the IdentityManager instance (for smart_agent.py compatibility).
        
        Returns:
            IdentityManager instance
        """
        return self._identity_manager
