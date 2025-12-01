"""
Redis Rate Limiter

Implements token bucket rate limiting using Redis.
This is the rate limiter for cloud mode.
"""

import logging
import redis
from core.interfaces import IRateLimiter

logger = logging.getLogger(__name__)


class RedisRateLimiter(IRateLimiter):
    """
    Redis-based rate limiter for cloud mode.
    
    Implements a simple counter-based rate limiting strategy:
    - Each agent gets a counter in Redis
    - Counter increments on each request
    - Counter expires after the time window
    - Requests are blocked if counter exceeds limit
    
    Fail-open design: If Redis is unavailable, allows traffic through.
    """
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, 
                 redis_db: int = 0, fail_open: bool = True):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            redis_db: Redis database number
            fail_open: If True, allow traffic when Redis is unavailable
        """
        self.fail_open = fail_open
        
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                socket_connect_timeout=0.1,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info(f"Redis rate limiter initialized: {redis_host}:{redis_port}")
            self.redis_available = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            if fail_open:
                logger.warning("Fail-open enabled: Traffic will be allowed")
            self.redis_available = False
            self.redis_client = None
    
    def check_limit(self, agent_id: str, limit: int = 10, window: int = 60) -> bool:
        """
        Check if an agent is within rate limits.
        
        Args:
            agent_id: The agent identifier
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            True if within limits
            
        Raises:
            Exception if limit exceeded (for fail-fast behavior)
        """
        if not self.redis_available:
            if self.fail_open:
                return True
            raise Exception("Rate limiting service unavailable")
        
        key = f"rate_limit:{agent_id}"
        
        try:
            current_count = self.redis_client.incr(key)
            
            # Set expiry on first request
            if current_count == 1:
                self.redis_client.expire(key, window)
            
            if current_count > limit:
                logger.warning(f"⛔ RATE LIMIT EXCEEDED for {agent_id}: {current_count}/{limit}")
                raise Exception(f"Rate limit exceeded ({limit} req/{window}s)")
            
            logger.debug(f"Rate limit check for {agent_id}: {current_count}/{limit}")
            return True
            
        except redis.RedisError as e:
            logger.error(f"Redis runtime error: {e}")
            if self.fail_open:
                logger.warning("Redis error - allowing traffic (fail-open)")
                return True
            raise
