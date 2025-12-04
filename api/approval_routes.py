"""
Approval API Routes for Human-in-the-Loop (HITL)

Provides endpoints for agents to request human approval and submit decisions.
"""

import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from typing import Dict, Any

from core.approval import Approval
from core.protocol import AmorceProtocol

# Create Blueprint
approval_bp = Blueprint('approvals', __name__, url_prefix='/v1/approvals')

# Storage will be injected from main orchestrator
_storage = None


def init_approval_routes(storage):
    """Initialize approval routes with storage dependency."""
    global _storage
    _storage = storage


@approval_bp.route('/create', methods=['POST'])
def create_approval():
    """
    Agent requests human approval for a transaction.
    
    Request body:
    {
        "transaction_id": "tx_abc123",
        "summary": "Book table for 4 at Le Petit Bistro, 7pm",
        "details": {...},
        "alternatives": [...],  // Optional
        "timeout_seconds": 3600  // Optional, default 1 hour
    }
    
    Response:
    {
        "status": "success",
        "approval_id": "apr_xyz789",
        "expires_at": "2025-12-02T05:30:00Z"
    }
    """
    try:
        body = request.json
        agent_id = request.headers.get('X-Agent-ID')
        
        if not agent_id:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                "Missing X-Agent-ID header"
            )), 400
        
        # Validate request
        if not body.get('transaction_id') or not body.get('summary'):
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                "Missing required fields: transaction_id, summary"
            )), 400
        
        # Generate approval ID
        approval_id = f"apr_{secrets.token_urlsafe(16)}"
        
        # Calculate expiry
        timeout_seconds = body.get('timeout_seconds', 3600)  # Default 1 hour
        expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        # Create approval
        approval = Approval(
            approval_id=approval_id,
            transaction_id=body['transaction_id'],
agent_id=agent_id,
            summary=body['summary'],
            details=body.get('details', {}),
            alternatives=body.get('alternatives'),
            expires_at=expires_at
        )
        
        # Store approval
        _storage.store_approval(approval.to_dict())
        
        return jsonify({
            "status": "success",
            "approval_id": approval_id,
            "expires_at": expires_at.isoformat()
        }), 201
        
    except Exception as e:
        return jsonify(AmorceProtocol.create_error_response(
            AmorceProtocol.ERROR_INTERNAL,
            f"Failed to create approval: {str(e)}"
        )), 500


@approval_bp.route('/<approval_id>', methods=['GET'])
def get_approval(approval_id: str):
    """
    Get approval status (agent polls this).
    
    Response:
    {
        "approval_id": "apr_xyz789",
        "status": "pending" | "approved" | "rejected" | "expired",
        "approved_by": "user@example.com",  // If approved
        "approved_at": "2025-12-02T04:30:00Z",
        "selected_alternative": 0,  // If applicable
        "comments": "Looks good"
    }
    """
    try:
        agent_id = request.headers.get('X-Agent-ID')
        
        if not agent_id:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                "Missing X-Agent-ID header"
            )), 400
        
        # Get approval from storage
        approval_data = _storage.get_approval(approval_id)
        
        if not approval_data:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_NOT_FOUND,
                f"Approval {approval_id} not found"
            )), 404
        
        approval = Approval.from_dict(approval_data)
        
        # Verify ownership
        if approval.agent_id != agent_id:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_FORBIDDEN,
                "Unauthorized access to approval"
            )), 403
        
        # Check if expired
        if approval.status == "pending" and approval.expires_at and datetime.utcnow() > approval.expires_at:
            approval.status = "expired"
            _storage.store_approval(approval.to_dict())
        
        return jsonify({
            "approval_id": approval.approval_id,
            "status": approval.status,
            "approved_by": approval.approved_by,
            "approved_at": approval.approved_at.isoformat() if approval.approved_at else None,
            "selected_alternative": approval.selected_alternative,
            "comments": approval.comments
        }), 200
        
    except Exception as e:
        return jsonify(AmorceProtocol.create_error_response(
            AmorceProtocol.ERROR_INTERNAL,
            f"Failed to get approval: {str(e)}"
        )), 500


@approval_bp.route('/<approval_id>/submit', methods=['POST'])
def submit_approval(approval_id: str):
    """
    Submit approval decision (called by agent after getting human response).
    
    Request body:
    {
        "decision": "approve" | "reject",
        "approved_by": "user@example.com",  // Human identifier
        "selected_alternative": 0,  // Optional
        "comments": "Looks good"  // Optional
    }
    
    Response:
    {
        "status": "success",
        "decision": "approved"
    }
    """
    try:
        body = request.json
        agent_id = request.headers.get('X-Agent-ID')
        
        if not agent_id:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                "Missing X-Agent-ID header"
            )), 400
        
        # Validate decision
        decision = body.get('decision')
        if decision not in ['approve', 'reject']:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                "Invalid decision. Must be 'approve' or 'reject'"
            )), 400
        
        # Get approval
        approval_data = _storage.get_approval(approval_id)
        
        if not approval_data:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_NOT_FOUND,
                f"Approval {approval_id} not found"
            )), 404
        
        approval = Approval.from_dict(approval_data)
        
        # Verify ownership
        if approval.agent_id != agent_id:
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_FORBIDDEN,
                "Unauthorized access to approval"
            )), 403
        
        # Check if already decided
        if approval.status != "pending":
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                f"Approval already {approval.status}"
            )), 400
        
        # Check if expired
        if approval.expires_at and datetime.utcnow() > approval.expires_at:
            approval.status = "expired"
            _storage.store_approval(approval.to_dict())
            return jsonify(AmorceProtocol.create_error_response(
                AmorceProtocol.ERROR_BAD_REQUEST,
                "Approval has expired"
            )), 400
        
        # Update approval
        approval.status = "approved" if decision == "approve" else "rejected"
        approval.approved_by = body.get('approved_by', 'unknown')
        approval.approved_at = datetime.utcnow()
        approval.selected_alternative = body.get('selected_alternative')
        approval.comments = body.get('comments')
        
        # Store updated approval
        _storage.store_approval(approval.to_dict())
        
        return jsonify({
            "status": "success",
            "decision": approval.status
        }), 200
        
    except Exception as e:
        return jsonify(AmorceProtocol.create_error_response(
            AmorceProtocol.ERROR_INTERNAL,
            f"Failed to submit approval: {str(e)}"
        )), 500
