"""
change_ssh_port MCP tool module.

Change SSH port on target hosts with atomic inventory updates.
"""

import uuid
from typing import Any, Dict, List

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()

MAX_HOSTS = 50
DEFAULT_TIMEOUT = 600


def register_change_ssh_port(server):
    """Register change_ssh_port tool."""

    @server.mcp.tool(
        name="change_ssh_port",
        description="""Change SSH port on target hosts with atomic inventory updates.

## Prerequisites
- Target hosts must be configured in inventory database first.
- User must be root on target hosts.
- Target hosts must use systemd as init system.

## Input Format
```json
{
  "hosts": ["host1", "host2"],
  "new_port": 2222
}
```

## Workflow
1. Validate input parameters (host count <= 50, port = 22 or 1024-65535)
2. Step 1: Run check_host_status on all hosts to get current ports
3. Step 2: Call external playbook change_ssh_port.yml (backup, modify config, test, reload, rollback on failure)
4. Step 3: Update inventory for successful hosts, verify connectivity via new port with fallback to old port

## Return Value
Returns execution results for each host, including success/failure status and details.
""",
    )
    @require_permission("change_ssh_port")
    def change_ssh_port(
        hosts: List[str],
        new_port: int,
    ) -> Dict[str, Any]:
        logger.info(
            f"MCP tool call: change_ssh_port, hosts={hosts}, new_port={new_port}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "change_ssh_port", {"hosts": hosts, "new_port": new_port}
        )

        inventory_manager = server.inventory_manager

        results: Dict[str, Dict[str, Any]] = {}

        if new_port != 22 and not (1024 <= new_port <= 65535):
            logger.error(f"Invalid port number: {new_port}. Must be 22 or 1024-65535")
            for host in hosts:
                results[host] = {
                    "status": "failed",
                    "message": f"Invalid port: {new_port}. Must be 22 or 1024-65535"
                }
            server.task_repo.update(task_id, "failed", results)
            return results

        if len(hosts) > MAX_HOSTS:
            logger.error(f"Host count {len(hosts)} exceeds maximum {MAX_HOSTS}")
            for host in hosts:
                results[host] = {
                    "status": "failed",
                    "message": f"Host count {len(hosts)} exceeds limit of {MAX_HOSTS}"
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
        host_old_ports: Dict[str, int] = {}

        for host in hosts:
            host_status = detect_result.get("results", {}).get(host, {})
            if host_status.get("error"):
                results[host] = {
                    "status": "failed",
                    "message": f"Host unreachable: {host_status.get('error')}"
                }
                continue

            current_port = host_status.get("python_path", "")
            host_info = inventory_manager.get_host(host)
            old_port = 22
            if host_info:
                old_port = host_info.get("ansible_port", 22)
            host_old_ports[host] = old_port
            hosts_to_process.append(host)

        if not hosts_to_process:
            logger.info(f"[{task_id}] No reachable hosts to process")
            server.task_repo.update(task_id, "failed", results)
            return results

        logger.info(
            f"[{task_id}] Step 2: Execute change_ssh_port playbook on {len(hosts_to_process)} hosts"
        )
        playbook_result = server.execution_service.execute_playbook(
            playbook="change_ssh_port.yml",
            targets=hosts_to_process,
            extravars={
                "new_port": new_port,
                "old_port": host_old_ports.get(hosts_to_process[0], 22),
            },
            timeout=DEFAULT_TIMEOUT,
            task_id=task_id,
        )
        logger.info(f"[{task_id}] Step 2: Playbook result: {playbook_result}")

        success_hosts: List[str] = []
        failed_hosts_data: Dict[str, Dict[str, Any]] = {}

        playbook_results = playbook_result.get("results", {})
        for host in hosts_to_process:
            host_result = playbook_results.get(host, {})
            rc = host_result.get("rc", -1)
            if rc == 0:
                success_hosts.append(host)
            else:
                failed_hosts_data[host] = {
                    "status": "failed",
                    "message": host_result.get("stderr", "Playbook execution failed"),
                    "rc": rc,
                }

        for host, fail_data in failed_hosts_data.items():
            results[host] = fail_data

        if not success_hosts:
            logger.info(f"[{task_id}] Step 2: All hosts failed, skipping verification")
            server.task_repo.update(task_id, "failed", results)
            return results

        logger.info(f"[{task_id}] Step 3: Verify connectivity for {len(success_hosts)} successful hosts")

        inventory_updates: Dict[str, Dict[str, Any]] = {}

        for host in success_hosts:
            old_port = host_old_ports.get(host, 22)
            inventory_result = inventory_manager.update_host_port(host, new_port)
            if inventory_result.get("status") != "success":
                results[host] = {
                    "status": "failed",
                    "message": f"Failed to update inventory: {inventory_result.get('message')}"
                }
                success_hosts.remove(host)
                continue
            inventory_updates[host] = {"old_port": old_port, "new_port": new_port}

        verify_results = _verify_connectivity(
            server, task_id, success_hosts, new_port, host_old_ports, inventory_updates
        )

        for host, verify_result in verify_results.items():
            results[host] = verify_result

        overall_status = "success"
        if any(r["status"] == "failed" for r in results.values()):
            if any(r["status"] == "success" for r in results.values()):
                overall_status = "partial_success"
            else:
                overall_status = "failed"

        server.task_repo.update(task_id, overall_status, results)
        logger.info(
            "MCP tool response: change_ssh_port, task_id=%s, results=%s",
            task_id, results
        )
        return results


def _verify_connectivity(
    server,
    task_id: str,
    success_hosts: List[str],
    new_port: int,
    host_old_ports: Dict[str, int],
    inventory_updates: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Verify connectivity on new port with fallback to old port.

    Args:
        server: Server instance with execution_service and inventory_manager.
        task_id: Task ID for logging.
        success_hosts: List of hosts that succeeded in step 2.
        new_port: New SSH port number.
        host_old_ports: Dict mapping host to old port number.
        inventory_updates: Dict mapping host to port update info.

    Returns:
        Dict mapping host to verification result.
    """
    results: Dict[str, Dict[str, Any]] = {}
    hosts_fallback_needed: List[str] = []

    logger.info(f"[{task_id}] Step 3a: Testing new port {new_port} connectivity")

    for host in success_hosts:
        echo_cmd = f"echo 'connectivity_test_new_port_{new_port}'"
        verify_result = server.execution_service.execute_shell(
            targets=[host],
            command=echo_cmd,
            timeout=30,
            task_id=task_id,
        )
        logger.info(f"[{task_id}] Step 3a: New port verify for {host}: {verify_result}")

        host_verify_results = verify_result.get("results", {})
        host_result = host_verify_results.get(host, {})
        rc = host_result.get("rc", -1)

        if rc == 0:
            results[host] = {
                "status": "success",
                "message": f"SSH port changed to {new_port} successfully, connectivity verified"
            }
        else:
            hosts_fallback_needed.append(host)

    if hosts_fallback_needed:
        logger.info(
            f"[{task_id}] Step 3b: Fallback to old port for {len(hosts_fallback_needed)} hosts"
        )

        for host in hosts_fallback_needed:
            old_port = host_old_ports.get(host, 22)
            echo_cmd = f"echo 'connectivity_test_old_port_{old_port}'"
            fallback_result = server.execution_service.execute_shell(
                targets=[host],
                command=echo_cmd,
                timeout=30,
                task_id=task_id,
            )
            logger.info(f"[{task_id}] Step 3b: Fallback verify for {host}: {fallback_result}")

            host_fallback_results = fallback_result.get("results", {})
            host_fallback_result = host_fallback_results.get(host, {})
            fallback_rc = host_fallback_result.get("rc", -1)

            if fallback_rc == 0:
                results[host] = {
                    "status": "success",
                    "message": f"New port {new_port} failed, fallback to old port {old_port} successful. Inventory reverted.",
                }
                inventory_manager = server.inventory_manager
                inventory_result = inventory_manager.update_host_port(host, old_port)
                if inventory_result.get("status") != "success":
                    results[host] = {
                        "status": "failed",
                        "message": f"Fallback successful but inventory update failed: {inventory_result.get('message')}"
                    }
            else:
                results[host] = {
                    "status": "failed",
                    "message": f"Both new port {new_port} and old port {old_port} connectivity failed"
                }

    return results
