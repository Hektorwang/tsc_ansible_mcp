"""
change_ssh_port MCP tool module.

Change SSH port on target hosts with atomic inventory updates.
"""

import uuid
from typing import Any, Dict, List

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


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
1. Validate input parameters
2. For each host:
   - Verify host exists in database
   - Get current SSH port
   - Backup sshd_config with task ID
   - Update SSH port in sshd_config
   - Test configuration with sshd -t
   - Reload sshd service
   - Test connection with new port
   - Update inventory database and YAML if successful
   - Rollback if any step fails

## Return Value
Returns execution results for each host, including success/failure status and details.
""",
    )
    @require_permission("change_ssh_port")
    def change_ssh_port(
        hosts: List[str],
        new_port: int,
    ) -> Dict[str, Any]:

        # Validate port range
        if not 1 <= new_port <= 65535:
            logger.error(f"Invalid port number: {new_port}. Must be between 1 and 65535")
            results = {}
            for host in hosts:
                results[host] = {
                    "status": "error",
                    "message": f"Invalid port number: {new_port}. Must be between 1 and 65535"
                }
            task_id = str(uuid.uuid4())
            server.task_repo.create(
                task_id, "change_ssh_port", {"hosts": hosts, "new_port": new_port}
            )
            server.task_repo.update(task_id, "failed", results)
            return results

        logger.info(
            f"MCP tool call: change_ssh_port, hosts={hosts}, new_port={new_port}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "change_ssh_port", {"hosts": hosts, "new_port": new_port}
        )

        inventory_manager = server.inventory_manager
        results = {}

        for host in hosts:
            results[host] = {
                "status": "pending",
                "message": "Initializing"
            }

            try:
                current_port = 22  # Default port in case of early failure
                # Verify host exists in database
                host_info = inventory_manager.get_host(host)
                if not host_info:
                    results[host] = {
                        "status": "error",
                        "message": f"Host {host} not found in inventory"
                    }
                    continue

                current_port = host_info.get("ansible_port", 22)
                logger.info(f"Current port for {host}: {current_port}")

                # Step 1: Backup sshd_config
                backup_cmd = f"cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.{task_id}"
                backup_result = server.execution_service.execute_shell(
                    [host], backup_cmd, task_id=task_id
                )
                if backup_result.get(host, {}).get("rc", 0) != 0:
                    results[host] = {
                        "status": "error",
                        "message": f"Failed to backup sshd_config: {backup_result.get(host, {}).get('stderr', 'Unknown error')}"
                    }
                    continue

                # Step 2: Update SSH port
                update_cmd = f"sed -i 's/^#*Port .*/Port {new_port}/' /etc/ssh/sshd_config"
                update_result = server.execution_service.execute_shell(
                    [host], update_cmd, task_id=task_id
                )
                if update_result.get(host, {}).get("rc", 0) != 0:
                    results[host] = {
                        "status": "error",
                        "message": f"Failed to update SSH port: {update_result.get(host, {}).get('stderr', 'Unknown error')}"
                    }
                    # Rollback
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    continue

                # Step 3: Test sshd configuration
                test_cmd = "sshd -t"
                test_result = server.execution_service.execute_shell(
                    [host], test_cmd, task_id=task_id
                )
                if test_result.get(host, {}).get("rc", 0) != 0:
                    results[host] = {
                        "status": "error",
                        "message": f"sshd configuration test failed: {test_result.get(host, {}).get('stderr', 'Unknown error')}"
                    }
                    # Rollback
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    continue

                # Step 4: Reload sshd service
                reload_cmd = "systemctl reload sshd"
                reload_result = server.execution_service.execute_shell(
                    [host], reload_cmd, task_id=task_id
                )
                if reload_result.get(host, {}).get("rc", 0) != 0:
                    results[host] = {
                        "status": "error",
                        "message": f"Failed to reload sshd: {reload_result.get(host, {}).get('stderr', 'Unknown error')}"
                    }
                    # Rollback
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    continue

                # Step 5: Test port availability
                port_test_cmd = f"ss -tln | grep :{new_port} || lsof -i :{new_port}"
                port_test_result = server.execution_service.execute_shell(
                    [host], port_test_cmd, task_id=task_id
                )
                if port_test_result.get(host, {}).get("rc", 0) != 0:
                    results[host] = {
                        "status": "error",
                        "message": f"Port {new_port} not available"
                    }
                    # Rollback
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    continue

                # Step 6: Test connection with new port and update inventory atomically
                # Temporarily update inventory to test new port
                temp_inventory_result = inventory_manager.update_host_port(host, new_port)
                if temp_inventory_result.get("status") != "success":
                    results[host] = {
                        "status": "error",
                        "message": f"Failed to update inventory: {temp_inventory_result.get('message', 'Unknown error')}"
                    }
                    # Rollback sshd config
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    continue

                # Test connection with new port
                test_conn_cmd = 'echo "Connection test"'
                test_conn_result = server.execution_service.execute_shell(
                    [host], test_conn_cmd, task_id=task_id
                )
                if test_conn_result.get(host, {}).get("rc", 0) != 0:
                    results[host] = {
                        "status": "error",
                        "message": f"Failed to connect with new port: {test_conn_result.get(host, {}).get('stderr', 'Unknown error')}"
                    }
                    # Rollback sshd config
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    # Rollback inventory
                    inventory_manager.update_host_port(host, current_port)
                    continue

                # All steps successful
                results[host] = {
                    "status": "success",
                    "message": f"SSH port changed to {new_port} successfully",
                    "old_port": current_port,
                    "new_port": new_port
                }

            except Exception as e:
                logger.error(f"Error processing host {host}: {str(e)}")
                results[host] = {
                    "status": "error",
                    "message": f"Unexpected error: {str(e)}"
                }
                # Attempt rollback
                try:
                    rollback_cmd = f"cp /etc/ssh/sshd_config.bak.{task_id} /etc/ssh/sshd_config && systemctl reload sshd"
                    server.execution_service.execute_shell([host], rollback_cmd, task_id=task_id)
                    inventory_manager.update_host_port(host, current_port)
                except Exception as rollback_error:
                    logger.error(f"Rollback failed for {host}: {str(rollback_error)}")

        server.task_repo.update(task_id, "success", results)
        logger.info(
            "MCP tool response: change_ssh_port, task_id=%s, results=%s",
            task_id, results
        )
        return results
