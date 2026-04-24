#!/usr/bin/env python3
"""
Execute SSH port change script on target host.

Uses standard library, compatible with tsc_python.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time

SSHD_CONFIG = "/etc/ssh/sshd_config"


def run_cmd(cmd, check=True):
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


def get_current_port():
    """Read current Port from sshd_config.

    Returns:
        Current SSH port number (defaults to 22).
    """
    if not os.path.exists(SSHD_CONFIG):
        return 22
    with open(SSHD_CONFIG, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("Port "):
                try:
                    return int(line.split()[1])
                except (IndexError, ValueError):
                    pass
    return 22


def backup_config(backup_path):
    """Backup sshd_config.

    Args:
        backup_path: Destination path for the backup.
    """
    shutil.copy2(SSHD_CONFIG, backup_path)


def restore_config(backup_path):
    """Restore sshd_config from backup.

    Args:
        backup_path: Source path of the backup file.
    """
    shutil.copy2(backup_path, SSHD_CONFIG)


def modify_config(new_port):
    """Modify the Port line in sshd_config.

    Args:
        new_port: New SSH port number.
    """
    with open(SSHD_CONFIG, "r") as f:
        lines = f.readlines()

    port_set = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Port "):
            new_lines.append(f"Port {new_port}\n")
            port_set = True
        else:
            new_lines.append(line)

    if not port_set:
        new_lines.append(f"Port {new_port}\n")

    with open(SSHD_CONFIG, "w") as f:
        f.writelines(new_lines)


def test_sshd_config():
    """Test sshd configuration validity.

    Returns:
        Tuple of (success, error_message).
    """
    result = subprocess.run("sshd -t", shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stderr.strip()


def reload_sshd():
    """Reload sshd service.

    Returns:
        Tuple of (success, error_message).
    """
    result = subprocess.run(
        "systemctl reload sshd", shell=True, capture_output=True, text=True
    )
    return result.returncode == 0, result.stderr.strip()


def restart_sshd():
    """Restart sshd service.

    Returns:
        Tuple of (success, error_message).
    """
    result = subprocess.run(
        "systemctl restart sshd", shell=True, capture_output=True, text=True
    )
    return result.returncode == 0, result.stderr.strip()


def is_port_listening(port):
    """Check if a port is listening.

    Args:
        port: Port number to check.

    Returns:
        True if port is listening, False otherwise.
    """
    result = subprocess.run(
        f"ss -tlnp | grep -q ':{port} '", shell=True, capture_output=True, text=True
    )
    return result.returncode == 0


def wait_for_port(port, timeout=15, interval=1):
    """Wait for a port to start listening.

    Args:
        port: Port number to wait for.
        timeout: Maximum wait time in seconds.
        interval: Polling interval in seconds.

    Returns:
        True if port is listening within timeout, False otherwise.
    """
    start = time.time()
    while time.time() - start < timeout:
        if is_port_listening(port):
            return True
        time.sleep(interval)
    return False


def main():
    """Main entry point for the SSH port change script."""
    parser = argparse.ArgumentParser(description="Change SSH port on target host")
    parser.add_argument("--new-port", type=int, required=True, help="New SSH port")
    parser.add_argument("--old-port", type=int, default=22, help="Old SSH port")
    parser.add_argument(
        "--backup-suffix", type=str, default=".bak", help="Backup file suffix"
    )
    args = parser.parse_args()

    new_port = args.new_port
    old_port = args.old_port
    backup_path = f"{SSHD_CONFIG}{args.backup_suffix}"

    try:
        backup_config(backup_path)
    except Exception as e:
        print(f"BACKUP_FAILED: {e}", file=sys.stderr)
        sys.exit(99)

    try:
        modify_config(new_port)
    except Exception as e:
        print(f"MODIFY_FAILED: {e}", file=sys.stderr)
        restore_config(backup_path)
        sys.exit(99)

    ok, err = test_sshd_config()
    if not ok:
        print(f"CONFIG_TEST_FAILED: {err}", file=sys.stderr)
        restore_config(backup_path)
        sys.exit(1)

    ok, err = reload_sshd()
    if not ok:
        print(f"RELOAD_FAILED: {err}", file=sys.stderr)
        restore_config(backup_path)
        ok2, _ = reload_sshd()
        if not ok2:
            ok3, err3 = restart_sshd()
            if not ok3:
                print(f"ROLLBACK_RELOAD_FAILED: {err3}", file=sys.stderr)
                sys.exit(2)
        sys.exit(2)

    if not wait_for_port(new_port, timeout=15):
        print(f"NEW_PORT_NOT_LISTENING: {new_port}", file=sys.stderr)
        restore_config(backup_path)
        ok, _ = reload_sshd()
        if not ok:
            restart_sshd()
        sys.exit(3)

    if old_port != 22 and old_port != new_port:
        if is_port_listening(old_port):
            print(f"OLD_PORT_STILL_LISTENING: {old_port}", file=sys.stderr)
            restore_config(backup_path)
            ok, _ = reload_sshd()
            if not ok:
                restart_sshd()
            sys.exit(4)

    print(f"SUCCESS: SSH port changed from {old_port} to {new_port}")
    sys.exit(0)


if __name__ == "__main__":
    main()
