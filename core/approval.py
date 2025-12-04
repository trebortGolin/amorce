"""
Approval Model for Human-in-the-Loop (HITL) Functionality

Enables agents to request human approval before proceeding with transactions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class Approval:
    """Represents a pending human approval request."""
    
    approval_id: str
    transaction_id: str
    agent_id: str
    
    # Request details
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    alternatives: Optional[List[Dict[str, Any]]] = None
    
    # State
    status: str = "pending"  # pending, approved, rejected, expired
    
    # Response (filled when human responds)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    selected_alternative: Optional[int] = None
    comments: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.utcnow())
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "approval_id": self.approval_id,
            "transaction_id": self.transaction_id,
            "agent_id": self.agent_id,
            "summary": self.summary,
            "details": self.details,
            "alternatives": self.alternatives,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "selected_alternative": self.selected_alternative,
            "comments": self.comments,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Approval":
        """Create from dictionary."""
        # Convert ISO string dates back to datetime
        created_at = datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at")
        approved_at = datetime.fromisoformat(data["approved_at"]) if data.get("approved_at") and isinstance(data["approved_at"], str) else data.get("approved_at")
        expires_at = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") and isinstance(data["expires_at"], str) else data.get("expires_at")
        
        return cls(
            approval_id=data["approval_id"],
            transaction_id=data["transaction_id"],
            agent_id=data["agent_id"],
            summary=data["summary"],
            details=data.get("details", {}),
            alternatives=data.get("alternatives"),
            status=data.get("status", "pending"),
            approved_by=data.get("approved_by"),
            approved_at=approved_at,
            selected_alternative=data.get("selected_alternative"),
            comments=data.get("comments"),
            created_at=created_at,
            expires_at=expires_at
        )
