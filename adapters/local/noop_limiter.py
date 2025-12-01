"""
No-Op Rate Limiter

Disables rate limiting for local development.
"""

import logging
from core.interfaces import IRateLimiter

logger = logging.getLogger(__name__)


class NoOpRateLimiter(IRateLimiter):
    """
    No-operation rate limiter for standalone mode.
    
    Always allows traffic through without any limits.
    This is appropriate for local development and testing.
    """
    
    def __init__(self):
        """Initialize the no-op rate limiter."""
        logger.info("Rate limiting disabled (NoOpRateLimiter)")
    
    def check_limit(self, agent_id: str, limit: int = 10, window: int = 60) -> bool:
        """
        Check rate limit (always passes).
        
        Args:
            agent_id: The agent identifier
            limit: Maximum requests (ignored)
            window: Time window in seconds (ignored)
            
        Returns:
            Always returns True
        """
        # No rate limiting in standalone mode
        return True
