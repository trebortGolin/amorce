"""
Local File-Based Agent Registry

Reads agent and service data from JSON configuration files.
This is the default registry for standalone mode.
"""

import json
import logging
import os
from typing import Optional, Dict, Any
from core.interfaces import IAgentRegistry

logger = logging.getLogger(__name__)


class LocalFileRegistry(IAgentRegistry):
    """
    File-based agent registry for standalone mode.
    
    Reads from:
    - config/agents.json: Agent registry (ID, public key, endpoint)
    - config/services.json: Service contracts (ID, provider, path template)
    """
    
    def __init__(self, agents_file: str = "./config/agents.json", 
                 services_file: str = "./config/services.json"):
        """
        Initialize the local file registry.
        
        Args:
            agents_file: Path to agents configuration file
            services_file: Path to services configuration file
        """
        self.agents_file = agents_file
        self.services_file = services_file
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._services: Dict[str, Dict[str, Any]] = {}
        
        self._load_agents()
        self._load_services()
    
    def _load_agents(self) -> None:
        """Load agents from JSON file."""
        if not os.path.exists(self.agents_file):
            logger.warning(f"Agents file not found: {self.agents_file}")
            logger.info("Creating empty agents registry.")
            self._agents = {}
            return
        
        try:
            with open(self.agents_file, 'r') as f:
                self._agents = json.load(f)
            logger.info(f"Loaded {len(self._agents)} agents from {self.agents_file}")
        except Exception as e:
            logger.error(f"Failed to load agents file: {e}")
            self._agents = {}
    
    def _load_services(self) -> None:
        """Load services from JSON file."""
        if not os.path.exists(self.services_file):
            logger.warning(f"Services file not found: {self.services_file}")
            logger.info("Creating empty services registry.")
            self._services = {}
            return
        
        try:
            with open(self.services_file, 'r') as f:
                self._services = json.load(f)
            logger.info(f"Loaded {len(self._services)} services from {self.services_file}")
        except Exception as e:
            logger.error(f"Failed to load services file: {e}")
            self._services = {}
    
    def find_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Find an agent by ID.
        
        Args:
            agent_id: The agent identifier
            
        Returns:
            Agent metadata or None if not found/inactive
        """
        agent = self._agents.get(agent_id)
        
        if not agent:
            logger.warning(f"Agent not found: {agent_id}")
            return None
        
        # Check if agent is active
        status = agent.get("metadata", {}).get("status", "active")
        if status != "active":
            logger.warning(f"Agent {agent_id} is not active (status: {status})")
            return None
        
        return agent
    
    def find_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a service contract by ID.
        
        Args:
            service_id: The service identifier
            
        Returns:
            Service contract or None if not found
        """
        service = self._services.get(service_id)
        
        if not service:
            logger.warning(f"Service not found: {service_id}")
            return None
        
        return service
    
    def list_agents(self) -> list[Dict[str, Any]]:
        """
        List all active agents.
        
        Returns:
            List of agent metadata dictionaries
        """
        active_agents = [
            agent for agent in self._agents.values()
            if agent.get("metadata", {}).get("status", "active") == "active"
        ]
        return active_agents
    
    def reload(self) -> None:
        """Reload agents and services from files (for hot-reload)."""
        logger.info("Reloading agent and service registries...")
        self._load_agents()
        self._load_services()
