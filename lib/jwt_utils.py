"""
JWT utility module.

Provides JWT generation, verification, key management, record management, and permission matching functionality.
"""

import json
import secrets
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt

from lib.tsc_logger import get_logger

logger = get_logger()

JWT_ALGORITHM = "HS256"
MIN_SECRET_KEY_LENGTH = 32


class JWTUtils:
    """JWT utility class."""

    def __init__(
        self,
        secret_key_file: Path,
        issued_tokens_file: Path,
        tool_permissions: Dict[str, List[str]],
    ):
        """Initialize JWT utility.

        Args:
            secret_key_file: Secret key file path.
            issued_tokens_file: Issued JWT records file path.
            tool_permissions: Role permission configuration.
        """
        self.secret_key_file = secret_key_file
        self.issued_tokens_file = issued_tokens_file
        self.tool_permissions = tool_permissions
        self.secret_key: str = ""
        self.issued_tokens: List[Dict[str, Any]] = []

        self._load_or_generate_secret_key()
        self._load_issued_tokens()

    def _load_or_generate_secret_key(self) -> None:
        """Load or generate secret key."""
        if self.secret_key_file.exists():
            key = self.secret_key_file.read_text().strip()
            if len(key) >= MIN_SECRET_KEY_LENGTH:
                self.secret_key = key
                logger.info(f"Loaded JWT secret key from file: {self.secret_key_file}")
                return
            else:
                logger.warning(
                    f"Secret key length insufficient ({len(key)} < {MIN_SECRET_KEY_LENGTH}), generating new key"
                )

        self.secret_key = self._generate_secret_key()
        self.secret_key_file.parent.mkdir(parents=True, exist_ok=True)
        self.secret_key_file.write_text(self.secret_key)
        logger.info(f"Generated JWT secret key and saved to: {self.secret_key_file}")

    def _generate_secret_key(self) -> str:
        """Generate secret key meeting length requirements.

        Returns:
            Generated secret key.
        """
        alphabet = string.ascii_letters + string.digits + "-_"
        key = "".join(secrets.choice(alphabet) for _ in range(48))
        return f"sk-jwt-{key}"

    def _load_issued_tokens(self) -> None:
        """Load issued JWT records."""
        if self.issued_tokens_file.exists():
            try:
                content = self.issued_tokens_file.read_text()
                data = json.loads(content)
                self.issued_tokens = data.get("tokens", [])
                logger.info(f"Loaded {len(self.issued_tokens)} issued JWT records")
            except Exception as e:
                logger.error(f"Failed to load JWT records: {e}")
                self.issued_tokens = []
        else:
            self.issued_tokens = []
            self._save_issued_tokens()
            logger.info(f"Created JWT records file: {self.issued_tokens_file}")

    def _save_issued_tokens(self) -> None:
        """Save issued JWT records."""
        self.issued_tokens_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"tokens": self.issued_tokens}
        self.issued_tokens_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )

    def generate_jwt(
        self,
        sub: str,
        name: str,
        role: str,
        expires_in: Optional[int] = None,
        description: Optional[str] = None,
    ) -> str:
        """Generate JWT.

        Args:
            sub: User unique identifier.
            name: User name.
            role: User role.
            expires_in: Expiration time (seconds), None means permanent.
            description: JWT description.

        Returns:
            Generated JWT string.
        """
        now = int(time.time())
        payload: Dict[str, Any] = {
            "sub": sub,
            "name": name,
            "role": role,
            "iat": now,
        }

        if expires_in:
            payload["exp"] = now + expires_in

        token = jwt.encode(payload, self.secret_key, algorithm=JWT_ALGORITHM)

        jwt_id = f"jwt_{sub}_{now}"
        expires_at = None
        if expires_in:
            expires_at = datetime.fromtimestamp(
                now + expires_in, tz=timezone.utc
            ).isoformat()

        record = {
            "jwt_id": jwt_id,
            "sub": sub,
            "name": name,
            "role": role,
            "issued_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "expires_at": expires_at,
            "description": description or "",
            "token": token,
        }

        self.issued_tokens.append(record)
        self._save_issued_tokens()

        logger.info(
            f"Generated JWT: sub={sub}, name={name}, role={role}, expires_in={expires_in}, token saved"
        )
        return token

    def _is_token_in_issued_records(self, token: str, payload: Dict[str, Any]) -> bool:
        """Return True if this JWT is still allowed by jwt_issued_tokens.json.

        Prefer matching the stored ``token`` string (v1.7.0+). If at least one
        record stores tokens, the bearer must match a row, except legacy rows
        with no ``token`` field where we allow the same ``sub`` as in the
        record. Removing a row and restarting drops it from memory so
        verification fails.
        """
        if not self.issued_tokens:
            logger.warning("JWT issued records are empty, verification denied")
            return False

        if any(r.get("token") == token for r in self.issued_tokens):
            return True

        has_stored_token = any(
            isinstance(r.get("token"), str) and r.get("token")
            for r in self.issued_tokens
        )
        if not has_stored_token:
            return True

        sub = payload.get("sub")
        if sub is not None and any(
            not r.get("token") and r.get("sub") == sub for r in self.issued_tokens
        ):
            return True

        logger.warning(
            "JWT signature valid but not in issued records, may have been removed from jwt_issued_tokens.json"
        )
        return False

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT.

        Args:
            token: JWT string.

        Returns:
            Payload if verification successful, None otherwise.
        """
        logger.debug(
            f"Starting JWT verification: token length={len(token)}, token prefix={token[:30]}..."
        )
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
            if not self._is_token_in_issued_records(token, payload):
                return None
            logger.debug(
                f"JWT verification successful: sub={payload.get('sub')}, name={payload.get('name')}, role={payload.get('role')}"
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(f"JWT expired: token={token[:30]}...")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT verification failed: {e}, token={token[:30]}...")
            return None

    def list_issued_tokens(self) -> List[Dict[str, Any]]:
        """List all issued JWTs.

        Returns:
            JWT records list.
        """
        return self.issued_tokens.copy()

    def revoke_jwt(self, jwt_id: str) -> bool:
        """Revoke JWT.

        Args:
            jwt_id: JWT ID.

        Returns:
            True if revoked successfully, False if not found.
        """
        for i, record in enumerate(self.issued_tokens):
            if record.get("jwt_id") == jwt_id:
                self.issued_tokens.pop(i)
                self._save_issued_tokens()
                logger.info(f"Revoked JWT: {jwt_id}")
                return True
        logger.warning(f"JWT not found: {jwt_id}")
        return False

    def check_permission(self, role: str, tool_name: str) -> bool:
        """Check if role has permission to call tool.

        Args:
            role: User role.
            tool_name: Tool name.

        Returns:
            True if has permission, False otherwise.
        """
        logger.debug(f"Checking permission: role={role}, tool={tool_name}")

        if role not in self.tool_permissions:
            logger.warning(
                f"Unknown role: {role}, available roles: {list(self.tool_permissions.keys())}"
            )
            return False

        permissions = self.tool_permissions[role]
        logger.debug(f"Role permissions list: role={role}, permissions={permissions}")

        for pattern in permissions:
            if self._match_permission(pattern, tool_name):
                logger.debug(
                    f"Permission match successful: role={role}, tool={tool_name}, pattern={pattern}"
                )
                return True

        logger.debug(
            f"Permission match failed: role={role}, tool={tool_name}, no matching pattern"
        )
        return False

    def _match_permission(self, pattern: str, tool_name: str) -> bool:
        """Match permission pattern.

        Args:
            pattern: Permission pattern (supports * and prefix matching).
            tool_name: Tool name.

        Returns:
            True if matched successfully.
        """
        logger.debug(
            f"Matching permission pattern: pattern={pattern}, tool={tool_name}"
        )

        if pattern == "*":
            logger.debug(f"Wildcard match: pattern={pattern}")
            return True

        if pattern.endswith("*"):
            prefix = pattern[:-1]
            matched = tool_name.startswith(prefix)
            logger.debug(
                f"Prefix match: pattern={pattern}, prefix={prefix}, matched={matched}"
            )
            return matched

        matched = pattern == tool_name
        logger.debug(
            f"Exact match: pattern={pattern}, tool={tool_name}, matched={matched}"
        )
        return matched

    def get_user_permissions(self, role: str) -> List[str]:
        """Get permissions list for role.

        Args:
            role: User role.

        Returns:
            List of permissions.
        """
        return self.tool_permissions.get(role, [])

    def regenerate_secret_key(self) -> str:
        """Regenerate secret key.

        Returns:
            New secret key.
        """
        self.secret_key = self._generate_secret_key()
        self.secret_key_file.write_text(self.secret_key)
        logger.warning(
            "Regenerated JWT secret key, all issued JWTs will be invalidated"
        )
        return self.secret_key
