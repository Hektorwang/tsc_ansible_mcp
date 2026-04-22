#!/usr/bin/env python3
"""
Password strength validation script for Ansible.

Validates that a password meets the following requirements:
- Length >= 8 characters
- Contains at least one digit
- Contains at least one letter (case-insensitive)
- Contains at least one special symbol

Usage:
    python3 validate_password.py <password>

Exit codes:
    0: Password is valid
    1: Password is invalid (prints error message to stderr)
"""

import re
import sys
from typing import Tuple


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength.

    Args:
        password: Password string to validate.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty string.
    """
    if len(password) < 8:
        return False, "Password length must be at least 8 characters"

    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit"

    if not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain at least one letter"

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:',.<>?/`~\\]", password):
        return False, "Password must contain at least one special symbol"

    return True, ""


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python3 validate_password.py <password>", file=sys.stderr)
        sys.exit(1)

    password = sys.argv[1]
    is_valid, error_msg = validate_password(password)

    if is_valid:
        print("Password validation passed")
        sys.exit(0)
    else:
        print(f"Password validation failed: {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
