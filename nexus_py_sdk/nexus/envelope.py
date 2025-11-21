"""
Nexus Envelope Module (Task 2)
Defines the strict NATP v0.1 data structure using Pydantic.
Handles canonical serialization and signing.
"""

import time
import uuid
import json
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

from .crypto import IdentityManager


# --- NATP Data Models ---

class SenderInfo(BaseModel):
    """Identifies the sender of the message."""
    public_key: str = Field(..., description="The sender's Ed25519 public key (PEM).")
    agent_id: Optional[str] = Field(None, description="Optional UUID of the agent.")


class SettlementInfo(BaseModel):
    """Economic metadata for the transaction."""
    amount: float = Field(0.0, description="Payment amount.")
    currency: str = Field("USD", description="Currency code (e.g., USD, NEX).")
    facilitation_fee: float = Field(0.0, description="Fee for the platform/facilitator.")


class NexusEnvelope(BaseModel):
    """
    The root NATP v0.1 Envelope.
    All transactions MUST use this structure.
    """
    natp_version: str = Field("0.1.0", description="Protocol version.")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique message ID.")
    timestamp: float = Field(default_factory=lambda: time.time(), description="Unix timestamp (UTC).")

    sender: SenderInfo
    payload: Dict[str, Any] = Field(..., description="The actual application data (intent, params).")
    settlement: SettlementInfo = Field(default_factory=SettlementInfo)

    signature: Optional[str] = Field(None, description="Ed25519 signature of the envelope content.")

    @field_validator('natp_version')
    @classmethod
    def check_version(cls, v: str) -> str:
        if v != "0.1.0":
            raise ValueError("Unsupported NATP version. Expected 0.1.0")
        return v

    def get_canonical_json(self) -> bytes:
        """
        Returns the canonical JSON bytes of the envelope WITHOUT the signature.
        This is what gets signed.
        """
        # 1. Create a copy of the model dump
        data = self.model_dump(mode='json', exclude={'signature'})

        # 2. Serialize strictly (sorted keys, no spaces)
        return json.dumps(
            data,
            sort_keys=True,
            separators=(',', ':')
        ).encode('utf-8')

    def sign(self, identity: IdentityManager) -> None:
        """
        Signs the envelope using the provided IdentityManager.
        Updates the .signature field in-place.
        """
        # 1. Get the canonical bytes
        canonical_bytes = self.get_canonical_json()

        # 2. Sign them
        self.signature = identity.sign_data(canonical_bytes)

    def verify(self) -> bool:
        """
        Verifies the envelope's signature against its own sender public key.
        """
        if not self.signature:
            return False

        canonical_bytes = self.get_canonical_json()
        return IdentityManager.verify_signature(
            self.sender.public_key,
            canonical_bytes,
            self.signature
        )