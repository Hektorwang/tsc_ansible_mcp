#!/usr/bin/env python3
"""
Execute password change script on target host.

Uses standard library, compatible with tsc_python.
Follows OOP principles as per SPEC.md.
"""

import argparse
import subprocess
import sys
from typing import Tuple


class PasswordChanger:
    """SSH password changer for target host."""

    ROOT_USER = "root"

    def __init__(self, new_password: str) -> None:
        """Initialize password changer.

        Args:
            new_password: New password to set.
        """
        self.new_password = new_password

    @staticmethod
    def _run_cmd(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
        """Execute a shell command and return the result.

        Args:
            cmd: Shell command string.
            check: Whether to raise on non-zero return code.

        Returns:
            CompletedProcess instance.
        """
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            raise RuntimeError(
                f"Command failed: {cmd}\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result

    def change_password(self) -> Tuple[bool, str]:
        """Change root password using chpasswd command.

        Returns:
            Tuple of (success, error_message).
        """
        cmd = f"echo '{self.ROOT_USER}:{self.new_password}' | chpasswd"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""

    def verify_password(self) -> bool:
        """Verify password was changed by testing authentication.

        Returns:
            True if password verification succeeds, False otherwise.
        """
        cmd = f"echo '{self.new_password}' | su -c 'echo password_verified' {self.ROOT_USER} 2>/dev/null"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0

    def execute(self) -> int:
        """Execute the password change operation.

        Returns:
            Exit code: 0=success, 1=change failed, 2=verification failed, 99=other error.
        """
        try:
            success, error = self.change_password()
            if not success:
                print(f"PASSWORD_CHANGE_FAILED: {error}", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"PASSWORD_CHANGE_FAILED: {e}", file=sys.stderr)
            return 99

        if not self.verify_password():
            print(
                "PASSWORD_VERIFICATION_FAILED: Password change may not have taken effect",
                file=sys.stderr,
            )
            return 2

        print("SUCCESS: Password changed successfully")
        return 0


def main() -> None:
    """Main entry point for the password change script."""
    parser = argparse.ArgumentParser(description="Change SSH password on target host")
    parser.add_argument(
        "--new-password", type=str, required=True, help="New SSH password"
    )
    args = parser.parse_args()

    changer = PasswordChanger(new_password=args.new_password)
    sys.exit(changer.execute())


if __name__ == "__main__":
    main()
