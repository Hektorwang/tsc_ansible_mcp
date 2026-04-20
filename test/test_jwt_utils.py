"""Unit tests for JWT Utils module."""

import tempfile
import time
from pathlib import Path

import pytest

from lib.jwt_utils import JWTUtils


class TestJWTUtils:
    """Test cases for JWTUtils class."""

    @pytest.fixture
    def jwt_utils(self):
        """Create JWTUtils instance for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            secret_key_file = Path(tmpdir) / "jwt_secret_key.txt"
            issued_tokens_file = Path(tmpdir) / "jwt_issued_tokens.json"

            tool_permissions = {
                "admin": ["*"],
                "user": ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"],
            }

            yield JWTUtils(
                secret_key_file=secret_key_file,
                issued_tokens_file=issued_tokens_file,
                tool_permissions=tool_permissions,
            )

    def test_generate_and_verify_jwt(self, jwt_utils):
        """Test JWT generation and verification."""
        token = jwt_utils.generate_jwt(
            sub="user_001",
            name="Test User",
            role="admin",
        )

        assert token is not None
        assert isinstance(token, str)

        # Verify the token
        payload = jwt_utils.verify_jwt(token)
        assert payload is not None
        assert payload["sub"] == "user_001"
        assert payload["name"] == "Test User"
        assert payload["role"] == "admin"

    def test_jwt_with_expiration(self, jwt_utils):
        """Test JWT with expiration time."""
        token = jwt_utils.generate_jwt(
            sub="user_002",
            name="Test User 2",
            role="user",
            expires_in=3600,  # 1 hour
        )

        payload = jwt_utils.verify_jwt(token)
        assert payload is not None
        assert "exp" in payload

    def test_jwt_expiration(self, jwt_utils):
        """Test JWT expiration."""
        # Generate token that expires in 1 second
        token = jwt_utils.generate_jwt(
            sub="user_003",
            name="Test User 3",
            role="user",
            expires_in=1,
        )

        # Verify immediately
        payload = jwt_utils.verify_jwt(token)
        assert payload is not None

        # Wait for expiration
        time.sleep(2)

        # Should fail verification after expiration
        payload = jwt_utils.verify_jwt(token)
        assert payload is None

    def test_check_permission_admin(self, jwt_utils):
        """Test admin permission check."""
        # Admin should have access to all tools
        assert jwt_utils.check_permission("admin", "ansible_shell") is True
        assert jwt_utils.check_permission("admin", "install_python") is True
        assert jwt_utils.check_permission("admin", "any_tool") is True

    def test_check_permission_user(self, jwt_utils):
        """Test user permission check."""
        # User should have limited access
        assert jwt_utils.check_permission("user", "list_playbooks") is True
        assert jwt_utils.check_permission("user", "ansible_playbook") is True
        assert jwt_utils.check_permission("user", "get_task_status") is True
        assert jwt_utils.check_permission("user", "playbook_test") is True  # playbook_* pattern
        assert jwt_utils.check_permission("user", "ansible_shell") is False
        assert jwt_utils.check_permission("user", "install_python") is False

    def test_list_issued_tokens(self, jwt_utils):
        """Test listing issued tokens."""
        # Generate some tokens
        jwt_utils.generate_jwt(sub="user_001", name="User 1", role="admin")
        jwt_utils.generate_jwt(sub="user_002", name="User 2", role="user")

        tokens = jwt_utils.list_issued_tokens()
        assert len(tokens) == 2

    def test_revoke_jwt(self, jwt_utils):
        """Test JWT revocation."""
        token = jwt_utils.generate_jwt(
            sub="user_001",
            name="Test User",
            role="admin",
        )

        # Get the jwt_id from issued tokens
        tokens = jwt_utils.list_issued_tokens()
        jwt_id = tokens[0]["jwt_id"]

        # Revoke the token
        result = jwt_utils.revoke_jwt(jwt_id)
        assert result is True

        # Token should no longer be in the list
        tokens = jwt_utils.list_issued_tokens()
        assert len(tokens) == 0

    def test_invalid_token_verification(self, jwt_utils):
        """Test verification of invalid token."""
        payload = jwt_utils.verify_jwt("invalid_token_string")
        assert payload is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
