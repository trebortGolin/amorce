"""
Cloud Directory Registry

Queries the Amorce Trust Directory API for agent discovery and public keys.
This is the registry implementation for cloud mode.
"""

import requests
import time
import logging
from typing import Optional, Dict, Any, Tuple
from core.interfaces import IAgentRegistry

logger = logging.getLogger(__name__)


class CloudDirectoryRegistry(IAgentRegistry):
    """
    Trust Directory-based agent registry for cloud mode.
    
    Queries the Amorce Trust Directory API for:
    - Agent lookup (public keys, endpoints)
    - Service contract lookup
    
    Implements caching with 5-minute TTL.
    """
    
    # Cache: {agent_id: (data, timestamp)}
    _agent_cache: Dict[str, Tuple[Dict, float]] = {}
    CACHE_TTL = 300  # 5 minutes
    
    def __init__(self, directory_url: str, timeout: int = 10):
        """
        Initialize the cloud directory registry.
        
        Args:
            directory_url: URL of the Amorce Trust Directory API
            timeout: Request timeout in seconds
        """
        if not directory_url:
            raise ValueError("TRUST_DIRECTORY_URL is required for cloud mode")
        
        self.directory_url = directory_url.rstrip('/')
        self.timeout = timeout
        
        logger.info(f"Cloud registry initialized: {self.directory_url}")
    
    def find_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Find an agent by querying the Trust Directory API.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            Agent metadata or None if not found/inactive
        """
        # Check cache first
        cached = self._agent_cache.get(agent_id)
        if cached and (time.time() - cached[1]) < self.CACHE_TTL:
            logger.debug(f"Cache hit for agent {agent_id}")
            return cached[0]
        
        # Query the Trust Directory
        try:
            url = f"{self.directory_url}/api/v1/lookup/{agent_id}"
            logger.debug(f"Querying Trust Directory: {url}")
            
            resp = requests.get(url, timeout=self.timeout)
            
            if resp.status_code != 200:
                logger.warning(f"Trust Directory lookup failed for {agent_id}: {resp.status_code}")
                return None
            
            data = resp.json()
            
            # Check if agent is active
            if data.get("status") != "active":
                logger.warning(f"Agent {agent_id} is not active (status: {data.get('status')})")
                return None
            
            # Cache the result
            self._agent_cache[agent_id] = (data, time.time())
            
            return data
            
        except requests.RequestException as e:
            logger.error(f"Error querying Trust Directory for agent {agent_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    def find_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a service contract by querying the Trust Directory API.
        
        Args:
            service_id: The service identifier
            
        Returns:
            Service contract or None if not found
        """
        try:
            url = f"{self.directory_url}/api/v1/services/{service_id}"
            logger.debug(f"Querying Trust Directory for service: {url}")
            
            resp = requests.get(url, timeout=self.timeout)
            
            if resp.status_code != 200:
                logger.warning(f"Service lookup failed for {service_id}: {resp.status_code}")
                return None
            
            return resp.json()
            
        except requests.RequestException as e:
            logger.error(f"Error querying Trust Directory for service {service_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    def list_agents(self) -> list[Dict[str, Any]]:
        """
        List all agents from the Trust Directory.
        
        Returns:
            List of agent metadata dictionaries
        """
        try:
            url = f"{self.directory_url}/api/v1/agents"
            logger.debug(f"Listing all agents from Trust Directory: {url}")
            
            resp = requests.get(url, timeout=self.timeout)
            
            if resp.status_code != 200:
                logger.error(f"Failed to list agents: {resp.status_code}")
                return []
            
            data = resp.json()
            return data.get("agents", [])
            
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return []
