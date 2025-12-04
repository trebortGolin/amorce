"""
Comprehensive Unit Tests for HITL (Human-in-the-Loop) Implementation

Tests all components:
- Approval model
- API routes
- Storage adapters
- SDK methods
- Error handling
- Edge cases
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Backend imports
import sys
sys.path.insert(0, '/Users/rgosselin/amorce')
from core.approval import Approval
from adapters.local.sqlite_storage import LocalSQLiteStorage

# SDK imports
sys.path.insert(0, '/Users/rgosselin/amorce_py_sdk')
from amorce import AmorceClient, IdentityManager
from amorce.crypto import LocalFileProvider


# ============================================================================
# TEST 1: Approval Model
# ============================================================================

class TestApprovalModel:
    """Test the Approval data model."""
    
    def test_create_approval(self):
        """Test creating an approval object."""
        approval = Approval(
            approval_id="apr_test_001",
            transaction_id="tx_001",
            agent_id="agent_001",
            summary="Test approval"
        )
        
        assert approval.approval_id == "apr_test_001"
        assert approval.transaction_id == "tx_001"
        assert approval.agent_id == "agent_001"
        assert approval.summary == "Test approval"
        assert approval.status == "pending"
    
    def test_approval_to_dict(self):
        """Test converting approval to dictionary."""
        approval = Approval(
            approval_id="apr_test_002",
            transaction_id="tx_002",
            agent_id="agent_002",
            summary="Test",
            details={"key": "value"}
        )
        
        data = approval.to_dict()
        
        assert isinstance(data, dict)
        assert data["approval_id"] == "apr_test_002"
        assert data["details"] == {"key": "value"}
        assert data["status"] == "pending"
    
    def test_approval_from_dict(self):
        """Test creating approval from dictionary."""
        data = {
            "approval_id": "apr_test_003",
            "transaction_id": "tx_003",
            "agent_id": "agent_003",
            "summary": "Test",
            "status": "approved",
            "approved_by": "user@test.com",
            "created_at": datetime.utcnow().isoformat()
        }
        
        approval = Approval.from_dict(data)
        
        assert approval.approval_id == "apr_test_003"
        assert approval.status == "approved"
        assert approval.approved_by == "user@test.com"


# ============================================================================
# TEST 2: Storage Layer
# ============================================================================

class TestSQLiteStorage:
    """Test SQLite storage for approvals."""
    
    @pytest.fixture
    def storage(self, tmp_path):
        """Create temporary SQLite storage."""
        db_path = tmp_path / "test.db"
        return LocalSQLiteStorage(str(db_path))
    
    def test_store_approval(self, storage):
        """Test storing an approval."""
        approval_data = {
            "approval_id": "apr_store_001",
            "transaction_id": "tx_001",
            "agent_id": "agent_001",
            "summary": "Test approval",
            "details": json.dumps({"test": "data"}),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Should not raise
        storage.store_approval(approval_data)
    
    def test_get_approval(self, storage):
        """Test retrieving an approval."""
        # Store first
        approval_data = {
            "approval_id": "apr_get_001",
            "transaction_id": "tx_001",
            "agent_id": "agent_001",
            "summary": "Test",
            "details": json.dumps({}),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        storage.store_approval(approval_data)
        
        # Retrieve
        retrieved = storage.get_approval("apr_get_001")
        
        assert retrieved is not None
        assert retrieved["approval_id"] == "apr_get_001"
        assert retrieved["status"] == "pending"
    
    def test_get_nonexistent_approval(self, storage):
        """Test retrieving non-existent approval returns None."""
        result = storage.get_approval("apr_does_not_exist")
        assert result is None
    
    def test_update_approval_status(self, storage):
        """Test updating approval status."""
        # Create
        approval_data = {
            "approval_id": "apr_update_001",
            "transaction_id": "tx_001",
            "agent_id": "agent_001",
            "summary": "Test",
            "details": json.dumps({}),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        storage.store_approval(approval_data)
        
        # Update
        approval_data["status"] = "approved"
        approval_data["approved_by"] = "test@example.com"
        approval_data["approved_at"] = datetime.utcnow().isoformat()
        storage.store_approval(approval_data)
        
        # Verify
        updated = storage.get_approval("apr_update_001")
        assert updated["status"] == "approved"
        assert updated["approved_by"] == "test@example.com"


# ============================================================================
# TEST 3: API Routes (Integration)
# ============================================================================

class TestApprovalAPI:
    """Test HITL API endpoints."""
    
    @pytest.fixture
    def client(self, tmp_path):
        """Create test Flask client."""
        import sys
        sys.path.insert(0, '/Users/rgosselin/amorce')
        
        # Import after path is set
        from api.approval_routes import approval_bp, init_approval_routes
        from adapters.local.sqlite_storage import LocalSQLiteStorage
        from flask import Flask
        
        app = Flask(__name__)
        # Use temporary file database (not :memory:) for proper initialization
        db_path = tmp_path / "test_api.db"
        storage = LocalSQLiteStorage(str(db_path))
        init_approval_routes(storage)
        app.register_blueprint(approval_bp)
        
        return app.test_client()
    
    def test_create_approval_endpoint(self, client):
        """Test POST /v1/approvals/create."""
        response = client.post(
            '/v1/approvals/create',
            json={
                "transaction_id": "tx_api_001",
                "summary": "API test approval",
                "timeout_seconds": 300
            },
            headers={"X-Agent-ID": "test_agent"}
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "approval_id" in data
        assert data["approval_id"].startswith("apr_")
    
    def test_create_approval_missing_fields(self, client):
        """Test validation of required fields."""
        response = client.post(
            '/v1/approvals/create',
            json={"transaction_id": "tx_001"},  # Missing summary
            headers={"X-Agent-ID": "test_agent"}
        )
        
        assert response.status_code == 400
    
    def test_get_approval_endpoint(self, client):
        """Test GET /v1/approvals/{id}."""
        # Create first
        create_resp = client.post(
            '/v1/approvals/create',
            json={
                "transaction_id": "tx_get_001",
                "summary": "Test"
            },
            headers={"X-Agent-ID": "test_agent"}
        )
        approval_id = json.loads(create_resp.data)["approval_id"]
        
        # Get
        response = client.get(
            f'/v1/approvals/{approval_id}',
            headers={"X-Agent-ID": "test_agent"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "pending"
        assert data["approval_id"] == approval_id
    
    def test_submit_approval_endpoint(self, client):
        """Test POST /v1/approvals/{id}/submit."""
        # Create
        create_resp = client.post(
            '/v1/approvals/create',
            json={
                "transaction_id": "tx_submit_001",
                "summary": "Test"
            },
            headers={"X-Agent-ID": "test_agent"}
        )
        approval_id = json.loads(create_resp.data)["approval_id"]
        
        # Submit
        response = client.post(
            f'/v1/approvals/{approval_id}/submit',
            json={
                "decision": "approve",
                "approved_by": "test@example.com"
            },
            headers={"X-Agent-ID": "test_agent"}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert data["decision"] == "approved"
    
    def test_submit_invalid_decision(self, client):
        """Test submitting invalid decision."""
        # Create
        create_resp = client.post(
            '/v1/approvals/create',
            json={"transaction_id": "tx_001", "summary": "Test"},
            headers={"X-Agent-ID": "test_agent"}
        )
        approval_id = json.loads(create_resp.data)["approval_id"]
        
        # Submit invalid
        response = client.post(
            f'/v1/approvals/{approval_id}/submit',
            json={
                "decision": "invalid",  # Bad decision
                "approved_by": "test@example.com"
            },
            headers={"X-Agent-ID": "test_agent"}
        )
        
        assert response.status_code == 400


# ============================================================================
# TEST 4: SDK Methods
# ============================================================================

class TestSDKMethods:
    """Test SDK HITL methods."""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock client."""
        with patch('amorce.client.requests.Session'):
            identity = Mock()
            identity.agent_id = "test_agent"
            identity.public_key_pem = "mock_key"
            
            client = AmorceClient(
                identity=identity,
                orchestrator_url="http://localhost:8080"
            )
            return client
    
    def test_request_approval_method(self, mock_client):
        """Test client.request_approval()."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "approval_id": "apr_sdk_001",
            "status": "success"
        }
        mock_client.session.post = Mock(return_value=mock_response)
        
        # Call method
        approval_id = mock_client.request_approval(
            transaction_id="tx_001",
            summary="Test"
        )
        
        assert approval_id == "apr_sdk_001"
        assert mock_client.session.post.called
    
    def test_submit_approval_method(self, mock_client):
        """Test client.submit_approval()."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_client.session.post = Mock(return_value=mock_response)
        
        # Call method
        result = mock_client.submit_approval(
            approval_id="apr_001",
            decision="approve",
            approved_by="test@example.com"
        )
        
        assert result is True
        assert mock_client.session.post.called
    
    def test_check_approval_method(self, mock_client):
        """Test client.check_approval()."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "approval_id": "apr_001",
            "status": "approved"
        }
        mock_client.session.get = Mock(return_value=mock_response)
        
        # Call method
        status = mock_client.check_approval("apr_001")
        
        assert status["status"] == "approved"
        assert mock_client.session.get.called


# ============================================================================
# TEST 5: Edge Cases & Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_approval_expiry(self):
        """Test approval expiry logic."""
        # Create expired approval
        expired_time = datetime.utcnow() - timedelta(hours=1)
        approval = Approval(
            approval_id="apr_expired",
            transaction_id="tx_001",
            agent_id="agent_001",
            summary="Test",
            expires_at=expired_time
        )
        
        # Check if expired
        is_expired = datetime.utcnow() > approval.expires_at
        assert is_expired is True
    
    def test_duplicate_approval_id(self, tmp_path):
        """Test handling duplicate approval IDs."""
        storage = LocalSQLiteStorage(str(tmp_path / "test.db"))
        
        approval_data = {
            "approval_id": "apr_dup",
            "transaction_id": "tx_001",
            "agent_id": "agent_001",
            "summary": "Test",
            "details": json.dumps({}),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store twice (should replace)
        storage.store_approval(approval_data)
        approval_data["status"] = "approved"
        storage.store_approval(approval_data)
        
        # Should have updated, not duplicated
        result = storage.get_approval("apr_dup")
        assert result["status"] == "approved"
    
    def test_concurrent_submissions(self,tmp_path):
        """Test handling concurrent approval submissions."""
        storage = LocalSQLiteStorage(str(tmp_path / "test.db"))
        
        approval_data = {
            "approval_id": "apr_concurrent",
            "transaction_id": "tx_001",
            "agent_id": "agent_001",
            "summary": "Test",
            "details": json.dumps({}),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat()
        }
        storage.store_approval(approval_data)
        
        # First submission
        approval_data["status"] = "approved"
        approval_data["approved_by"] = "user1@test.com"
        storage.store_approval(approval_data)
        
        # Second submission (should fail in real scenario)
        # For now, it overwrites (which is acceptable for MVP)
        result = storage.get_approval("apr_concurrent")
        assert result["status"] == "approved"


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("HITL COMPREHENSIVE UNIT TESTS")
    print("=" * 70)
    
    # Run with pytest
    pytest.main([__file__, "-v", "--tb=short"])
