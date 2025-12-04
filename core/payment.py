"""
Payment Infrastructure - Dormant Design for Phase 3

This module defines the payment protocol interfaces and data models
that will be used in Phase 3. The infrastructure is designed NOW but
remains DORMANT until payment features are enabled.

Design principles:
1. Add payment fields to existing transactions (optional)
2. Feature flag controlled (ENABLE_PAYMENTS=false by default)
3. No breaking changes to existing flows  
4. Payment becomes an optional step in the transaction lifecycle
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class PaymentStatus(Enum):
    """Payment lifecycle states."""
    NOT_REQUIRED = "not_required"      # Default - no payment needed
    PENDING = "pending"                 # Payment request created
    AUTHORIZED = "authorized"           # Funds escrowed
    CAPTURED = "captured"               # Funds transferred to merchant
    FAILED = "failed"                   # Payment failed
    REFUNDED = "refunded"               # Payment refunded


class PaymentMethod(Enum):
    """Supported payment methods."""
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"


@dataclass
class PaymentRequest:
    """
    Payment request from service provider.
    Added to transaction payload when service requires payment.
    """
    payment_request_id: str
    amount: float
    currency: str = "USD"
    description: str = ""
    recipient_agent_id: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "payment_request_id": self.payment_request_id,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "recipient_agent_id": self.recipient_agent_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


@dataclass
class Payment:
    """
    Payment record tracking the full payment lifecycle.
    Stored in database when payment is created.
    """
    payment_id: str
    payment_request_id: str
    transaction_id: str
    
    # Parties
    payer_agent_id: str
    payee_agent_id: str
    
    # Amount
    amount: float
    currency: str = "USD"
    
    # Payment method
    payment_method: str = PaymentMethod.CARD.value
    payment_token: Optional[str] = None  # Token from payment processor
    
    # Status
    status: str = PaymentStatus.PENDING.value
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    
    # Metadata
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "payment_id": self.payment_id,
            "payment_request_id": self.payment_request_id,
            "transaction_id": self.transaction_id,
            "payer_agent_id": self.payer_agent_id,
            "payee_agent_id": self.payee_agent_id,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "payment_token": self.payment_token,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "authorized_at": self.authorized_at.isoformat() if self.authorized_at else None,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "description": self.description,
            "metadata": self.metadata
        }


# Feature flag - controls whether payment features are active
ENABLE_PAYMENTS = False  # Set to True in Phase 3


def payment_required(transaction_data: Dict[str, Any]) -> bool:
    """
    Check if transaction requires payment.
    
    Returns False if payments are disabled (Phase 1/2).
    Returns True if transaction contains payment_request.
    """
    if not ENABLE_PAYMENTS:
        return False
    
    return "payment_request" in transaction_data.get("result", {})


def validate_payment_token(payment_token: str) -> bool:
    """
    Validate payment token (stub for Phase 3).
    
    In Phase 3, this will call Stripe/payment processor.
    For now, returns True (no-op).
    """
    if not ENABLE_PAYMENTS:
        return True  # No validation when payments disabled
    
    # Phase 3: Call payment processor API
    # stripe.PaymentIntent.retrieve(payment_token)
    return True


# Storage interface extensions (to be added to IStorage)
"""
class IStorage(ABC):
    # Existing methods...
    
    @abstractmethod
    def store_payment(self, payment_data: Dict[str, Any]) -> None:
        pass
    
    @abstractmethod
    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def update_payment_status(self, payment_id: str, status: str) -> None:
        pass
"""


# API routes (to be added in Phase 3)
"""
POST   /v1/payments/requests/create        # Service creates payment request
POST   /v1/payments/create                 # User agent creates payment
POST   /v1/payments/{id}/validate          # Service validates payment
GET    /v1/payments/{id}                   # Check payment status
"""


# Transaction payload extensions (optional fields)
"""
Transaction with payment (Phase 3):
{
    "transaction_id": "tx_abc123",
    "service_id": "airline_api",
    "consumer_agent_id": "agent_sarah",
    "payload": {...},
    
    // NEW: Optional payment fields
    "payment": {
        "payment_request_id": "preq_xyz789",
        "amount": 1200.00,
        "currency": "USD",
        "status": "pending"
    }
}
"""


if __name__ == "__main__":
    # Example: How payment will work in Phase 3
    print("Payment Infrastructure - Dormant")
    print(f"Payments enabled: {ENABLE_PAYMENTS}")
    print("\nPhase 3 will enable:")
    print("  1. Payment requests from services")
    print("  2. Payment creation by user agents")
    print("  3. Payment validation")
    print("  4. Stripe Connect integration")
    print("  5. 0.3% transaction fee")
