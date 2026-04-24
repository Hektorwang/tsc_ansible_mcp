"""
change_ssh_password MCP tool module.

Change SSH password on target hosts with atomic inventory updates.
"""

import re
import uuid
from typing import Any, Dict, List

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()

MAX_HOSTS = 50
DEFAULT_TIMEOUT = 600


def _validate_password(password: str) -> bool:
    """Validate password complexity.

    Args:
        password: Password string to validate.

    Returns:
        True if password meets complexity requirements, False otherwise.
    """
    if len(password) < 8:
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[a-zA-Z]", password):
        return False
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", password):
        return False
    return True


def register_change_ssh_password(server):
    """Register change_ssh_password tool."""

    @server.mcp.tool(
        name="change_ssh_password",
        description="""Change SSH password on target hosts with atomic inventory updates.

## Prerequisites
- Target hosts must be configured in inventory database first.
- User must be root on target hosts.
- Password must meet complexity requirements (8+ chars, digit, letter, special char).

## Input Format
```json
{
  "hosts": ["host1", "host2"],
  "new_password": "NewPass123!"
}
```

## Workflow
1. Validate input parameters (host count <= 50, password complexity)
2. Step 1: Run check_host_status on all hosts to get current environment
3. Step 2: Call external playbook change_ssh_password.yml (change password, local verification)
4. Step 3: Update inventory for successful hosts (playbook includes local verification)

## Return Value
Returns execution results for each host, including success/failure status and details.
""",
    )
    @require_permission("change_ssh_password")
    def change_ssh_password(
        hosts: List[str],
        new_password: str,
    ) -> Dict[str, Any]:
        logger.info(
            f"MCP tool call: change_ssh_password, hosts={hosts}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "change_ssh_password", {"hosts": hosts}
        )

        inventory_manager = server.inventory_manager

        results: Dict[str, Dict[str, Any]] = {}

        if not _validate_password(new_password):
            logger.error("Password does not meet complexity requirements")
            for host in hosts:
                results[host] = {
                    "status": "failed",
                    "message": "Password does not meet complexity requirements: must be 8+ chars, contain digit, letter, and special character",
                }
            server.task_repo.update(task_id, "failed", results)
            return results

        if len(hosts) > MAX_HOSTS:
            logger.error(f"Host count {len(hosts)} exceeds maximum {MAX_HOSTS}")
            for host in hosts:
                results[host] = {
                    "status": "failed",
                    "message": f"Host count {len(hosts)} exceeds limit of {MAX_HOSTS}",
                }
            server.task_repo.update(task_id, "failed", results)
            return results

        for host in hosts:
            results[host] = {"status": "pending", "message": "Initializing"}

        logger.info(f"[{task_id}] Step 1: Check host status for all hosts")
        detect_result = server.execution_service.check_host_status(
            targets=hosts,
            timeout=DEFAULT_TIMEOUT,
            task_id=task_id,
        )
        logger.info(f"[{task_id}] Step 1: Host status check result: {detect_result}")

        hosts_to_process: List[str] = []

        for host in hosts:
            host_status = detect_result.get("results", {}).get(host, {})
            if host_status.get("error"):
                results[host] = {
                    "status": "failed",
                    "message": f"Host unreachable: {host_status.get('error')}",
                }
                continue

            hosts_to_process.append(host)

        if not hosts_to_process:
            logger.info(f"[{task_id}] No reachable hosts to process")
            server.task_repo.update(task_id, "failed", results)
            return results

        logger.info(
            f"[{task_id}] Step 2: Execute change_ssh_password playbook on {len(hosts_to_process)} hosts"
        )
        playbook_result = server.execution_service.execute_playbook(
            playbook="change_ssh_password.yml",
            targets=hosts_to_process,
            extravars={
                "new_password": new_password,
            },
            timeout=DEFAULT_TIMEOUT,
            task_id=task_id,
        )
        logger.info(f"[{task_id}] Step 2: Playbook result: {playbook_result}")

        playbook_results = playbook_result.get("results", {})
        for host in hosts_to_process:
            host_result = playbook_results.get(host, {})
            rc = host_result.get("rc", -1)
            if rc == 0:
                inventory_result = inventory_manager.update_host_credentials(
                    host=host,
                    password=new_password,
                )
                if inventory_result.get("status") == "success":
                    results[host] = {
                        "status": "success",
                        "message": "SSH password changed and verified locally",
                    }
                else:
                    results[host] = {
                        "status": "failed",
                        "message": f"Password changed but failed to update inventory: {inventory_result.get('message')}",
                    }
            else:
                results[host] = {
                    "status": "failed",
                    "message": host_result.get("stderr", "Playbook execution failed"),
                    "rc": rc,
                }

        overall_status = "success"
        if any(r["status"] == "failed" for r in results.values()):
            if any(r["status"] == "success" for r in results.values()):
                overall_status = "partial_success"
            else:
                overall_status = "failed"

        server.task_repo.update(task_id, overall_status, results)
        logger.info(
            "MCP tool response: change_ssh_password, task_id=%s, results=%s",
            task_id,
            results,
        )
        return results
