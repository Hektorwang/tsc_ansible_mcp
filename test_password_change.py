#!/usr/bin/env python3
"""Test password change functionality using direct Ansible playbook call."""

import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()


def run_ansible_playbook(playbook_path: str, extravars: dict) -> dict:
    """Run Ansible playbook with given extravars."""
    cmd = [
        "ansible-playbook",
        str(playbook_path),
        "-i", str(BASE_DIR / "etc" / "inventory.yml"),
        "-l", "192.168.19.38",
        "-e", json.dumps(extravars),
        "-v",
    ]
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
    )
    print(f"Return code: {result.returncode}")
    print("=== STDOUT ===")
    print(result.stdout)
    print("=== STDERR ===")
    print(result.stderr)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    """Main entry point."""
    print("=== Testing password change for 192.168.19.38 ===")
    
    playbook_path = BASE_DIR / "playbooks" / "admin_change_ssh_config.yml"
    extravars = {
        "root_password": "1qaz@WSX",
    }
    
    result = run_ansible_playbook(str(playbook_path), extravars)
    
    print("\n=== Inventory after change ===")
    inventory_result = subprocess.run(
        [sys.executable, str(BASE_DIR / "bin" / "inventory.py"), "list"],
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
    )
    print(inventory_result.stdout)
    
    return result["returncode"]


if __name__ == "__main__":
    sys.exit(main())
