"""
Amorce Core - Protocol Logic

Pure AATP protocol implementation without infrastructure dependencies.
This module contains protocol-level validation, error codes, and message formats.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AmorceProtocol:
    """
    AATP Protocol implementation.
    
    Handles:
    - Message format validation
    - Error code generation
    - Protocol constants
    """
    
    # Protocol Version
    VERSION = "1.0.0"
    
    # Error Codes
    ERROR_BAD_REQUEST = "BAD_REQUEST"
    ERROR_UNAUTHORIZED = "UNAUTHORIZED"
    ERROR_FORBIDDEN = "FORBIDDEN"
    ERROR_NOT_FOUND = "NOT_FOUND"
    ERROR_RATE_LIMIT = "RATE_LIMIT_EXCEEDED"
    ERROR_INTERNAL = "INTERNAL_ERROR"
    ERROR_INVALID_SIGNATURE = "INVALID_SIGNATURE"
    
    @staticmethod
    def validate_transaction_request(body: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate a transaction request payload.
        
        Args:
            body: The request body
            
        Returns:
            (is_valid, error_message)
        """
        required_fields = ["consumer_agent_id", "service_id", "payload"]
        
        for field in required_fields:
            if field not in body:
                return False, f"Missing required field: {field}"
        
        # Validate consumer_agent_id format (basic check)
        consumer_id = body.get("consumer_agent_id")
        if not consumer_id or not isinstance(consumer_id, str):
            return False, "Invalid consumer_agent_id"
        
        # Validate service_id
        service_id = body.get("service_id")
        if not service_id or not isinstance(service_id, str):
            return False, "Invalid service_id"
        
        # Validate payload is a dict
        payload = body.get("payload")
        if not isinstance(payload, dict):
            return False, "Payload must be a JSON object"
        
        return True, None
    
    @staticmethod
    def create_error_response(error_code: str, message: str, details: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create a standardized error response.
        
        Args:
            error_code: Protocol error code
            message: Human-readable error message
            details: Optional additional details
            
        Returns:
            Error response dictionary
        """
        response = {
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if details:
            response["error"]["details"] = details
        
        return response
    
    @staticmethod
    def create_success_response(transaction_id: str, result: Any, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create a standardized success response.
        
        Args:
            transaction_id: The transaction identifier
            result: The result data from the provider
            metadata: Optional metadata
            
        Returns:
            Success response dictionary
        """
        response = {
            "transaction_id": transaction_id,
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result
        }
        
        if metadata:
            response["metadata"] = metadata
        
        return response
    
    @staticmethod
    def get_http_status_for_error(error_code: str) -> int:
        """
        Map protocol error codes to HTTP status codes.
        
        Args:
            error_code: Protocol error code
            
        Returns:
            HTTP status code
        """
        mapping = {
            AmorceProtocol.ERROR_BAD_REQUEST: 400,
            AmorceProtocol.ERROR_UNAUTHORIZED: 401,
            AmorceProtocol.ERROR_FORBIDDEN: 403,
            AmorceProtocol.ERROR_NOT_FOUND: 404,
            AmorceProtocol.ERROR_RATE_LIMIT: 429,
            AmorceProtocol.ERROR_INVALID_SIGNATURE: 403,
            AmorceProtocol.ERROR_INTERNAL: 500,
        }
        return mapping.get(error_code, 500)


class MessageValidator:
    """
    Validates AATP message formats and signatures.
    """
    
    @staticmethod
    def validate_headers(headers: Dict[str, str]) -> tuple[bool, Optional[str]]:
        """
        Validate required headers for a transaction.
        
        Args:
            headers: HTTP headers dict
            
        Returns:
            (is_valid, error_message)
        """
        # Check for signature header
        if "X-Agent-Signature" not in headers:
            return False, "Missing X-Agent-Signature header"
        
        signature = headers["X-Agent-Signature"]
        if not signature or not isinstance(signature, str):
            return False, "Invalid X-Agent-Signature format"
        
        return True, None
