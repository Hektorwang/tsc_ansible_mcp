"""
Ansible execution engine module.

Provides remote command execution, environment detection, Python installation, and other functions.
"""

import json
import re
import signal
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import ansible_runner
import yaml

from lib.ansible_logger import ansible_logger
from lib.config import Config
from lib.inventory_manager import InventoryManager
from lib.task_result_store import task_result_store
from lib.tsc_logger import get_logger

logger = get_logger()


class Executor:
    """Ansible execution engine."""

    def __init__(self, config: Config, inventory_manager: InventoryManager):
        self.config = config
        self.inventory_manager = inventory_manager
        ansible_logger._setup_from_config(config)
        self._active_hosts: set = set()
        self._lock = threading.Lock()
        self._current_task_hosts: List[str] = []
        self._original_signal_handler: dict = {}
        self._install_signal_handlers()

    def _acquire_hosts(self, hosts: List[str]) -> tuple[bool, List[str]]:
        """Attempt to acquire execution locks for hosts.

        Args:
            hosts: List of hosts to acquire locks for.

        Returns:
            tuple[bool, List[str]]: (success, busy_hosts) Whether acquisition was successful,
            and list of busy hosts.
        """
        logger.debug(f"[LOCK] Attempting to acquire locks for hosts: {hosts}")
        with self._lock:
            logger.debug(
                f"[LOCK] _acquire_hosts called: hosts={hosts}, current_active={list(self._active_hosts)}"
            )
            busy_hosts = [host for host in hosts if host in self._active_hosts]
            if busy_hosts:
                logger.warning(f"[LOCK] _acquire_hosts FAILED: hosts busy={busy_hosts}")
                logger.debug(f"[LOCK] Current active hosts: {list(self._active_hosts)}")
                return False, busy_hosts
            for host in hosts:
                self._active_hosts.add(host)
                logger.info(f"[LOCK] Acquired lock for host: {host}")
            logger.info(
                f"[LOCK] _acquire_hosts SUCCESS: hosts={hosts}, new_active={list(self._active_hosts)}"
            )
            return True, []

    def _release_hosts(self, hosts: List[str]) -> None:
        """Release execution locks for hosts.

        Args:
            hosts: List of hosts to release locks for.

        Returns:
            None
        """
        logger.debug(f"[LOCK] Attempting to release locks for hosts: {hosts}")
        with self._lock:
            logger.debug(
                f"[LOCK] _release_hosts called: hosts={hosts}, current_active={list(self._active_hosts)}"
            )
            released_hosts = []
            skipped_hosts = []
            for host in hosts:
                if host in self._active_hosts:
                    self._active_hosts.remove(host)
                    released_hosts.append(host)
                    logger.info(f"[LOCK] Released host lock: {host}")
                else:
                    skipped_hosts.append(host)
                    logger.debug(
                        f"[LOCK] Host {host} not in active hosts, skipping release"
                    )
            logger.info(
                f"[LOCK] _release_hosts done: released={released_hosts}, skipped={skipped_hosts}, remaining_active={list(self._active_hosts)}"
            )

    def _install_signal_handlers(self):
        """Install signal handlers to ensure locks are released."""

        def signal_handler(signum, frame):
            logger.warning(f"[SIGNAL] Received signal {signum}, releasing host locks...")
            with self._lock:
                if self._current_task_hosts:
                    logger.warning(f"[SIGNAL] Releasing locks: {self._current_task_hosts}")
                    for host in self._current_task_hosts:
                        if host in self._active_hosts:
                            self._active_hosts.remove(host)
                    self._current_task_hosts = []
            logger.warning("[SIGNAL] Host locks released, program exiting...")
            if signum == signal.SIGINT:
                raise KeyboardInterrupt("Ctrl+C interrupted")
            elif signum == signal.SIGTERM:
                raise SystemExit("SIGTERM received")

        self._original_signal_handler[signal.SIGINT] = signal.signal(
            signal.SIGINT, signal_handler
        )
        self._original_signal_handler[signal.SIGTERM] = signal.signal(
            signal.SIGTERM, signal_handler
        )

    def _restore_signal_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_signal_handler.items():
            signal.signal(sig, handler)

    def _build_summary_result(
        self,
        task_id: str,
        results: Dict[str, Dict[str, Any]],
        elapsed: float,
        task_type: str = "execution",
    ) -> Dict[str, Any]:
        """Build summary result for return.

        Args:
            task_id: Task ID.
            results: Execution results for all hosts.
            elapsed: Execution elapsed time.
            task_type: Task type.

        Returns:
            Summary result dictionary.
        """
        task_result_store.save_result(task_id, {"results": results, "elapsed": elapsed})

        total = len(results)
        success_count = sum(1 for r in results.values() if r.get("rc", 0) == 0)
        failed_count = total - success_count

        failed_hosts = [h for h, r in results.items() if r.get("rc", 0) != 0]

        max_failed_detail = self.config.max_failed_detail
        failed_detail = {}
        for host in failed_hosts[:max_failed_detail]:
            host_result = results[host].copy()
            max_len = self.config.max_output_length
            if "stdout" in host_result and len(host_result["stdout"]) > max_len:
                host_result["stdout"] = (
                    host_result["stdout"][: max_len // 2]
                    + "\n...[truncated]...\n"
                    + host_result["stdout"][-max_len // 2 :]
                )
            if "stderr" in host_result and len(host_result["stderr"]) > max_len:
                host_result["stderr"] = (
                    host_result["stderr"][: max_len // 2]
                    + "\n...[truncated]...\n"
                    + host_result["stderr"][-max_len // 2 :]
                )
            failed_detail[host] = host_result

        status = "success"
        if failed_count > 0:
            if success_count > 0:
                status = "partial_success"
            else:
                status = "failed"

        message = f"Execution completed, {failed_count} hosts failed"
        if failed_count > 0:
            message += f". Use get_task_detail('{task_id}', host) to view details"

        return {
            "task_id": task_id,
            "status": status,
            "summary": {
                "total": total,
                "success": success_count,
                "failed": failed_count,
            },
            "failed_hosts": failed_hosts,
            "failed_detail": failed_detail,
            "has_more_failed": len(failed_hosts) > max_failed_detail,
            "elapsed": f"{elapsed:.2f}s",
            "message": message,
        }

    def _build_inventory(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build Ansible inventory.

        Args:
            targets: List of target hosts.
            credentials: Credentials information provided by LLM.

        Returns:
            Ansible inventory dictionary.
        """
        inventory: Dict[str, Any] = {"all": {"hosts": {}}}
        for target in targets:
            # Special handling for localhost, using local connection instead of SSH
            if target == "localhost":
                host_data: Dict[str, Any] = {
                    "ansible_connection": "local",
                    "ansible_python_interpreter": "/usr/bin/python3",
                }
                logger.debug(f"Using local connection for localhost")
            else:
                host_data: Dict[str, Any] = {
                    "ansible_host": target,
                    "ansible_ssh_common_args": self.config.ssh_base_args,
                }

                cached_host = self.inventory_manager.get_host(target)

                # First use cached information (if available)
                if cached_host:
                    host_data.update(cached_host)
                    logger.debug(f"Using cached inventory info: {target}")
                    if "ansible_python_interpreter" in cached_host:
                        logger.debug(
                            f"Using cached Python interpreter: {cached_host['ansible_python_interpreter']}"
                        )

                # If new credentials provided, override cached information
                if credentials:
                    if "user" in credentials:
                        host_data["ansible_user"] = credentials["user"]
                    if "port" in credentials:
                        host_data["ansible_port"] = credentials["port"]
                    if "password" in credentials:
                        host_data["ansible_password"] = credentials["password"]
                        host_data["ansible_ssh_common_args"] = (
                            f"{self.config.ssh_base_args} {self.config.ssh_password_args}"
                        )
                        logger.debug(
                            f"Using provided credentials: {target}, SSH args: {host_data['ansible_ssh_common_args']}"
                        )
                    elif "private_key" in credentials:
                        host_data["ansible_ssh_private_key_file"] = credentials[
                            "private_key"
                        ]
                        host_data["ansible_ssh_common_args"] = self.config.ssh_base_args
                        logger.debug(
                            f"Using provided credentials: {target}, SSH args: {host_data['ansible_ssh_common_args']}"
                        )
                    else:
                        logger.debug(f"Using provided credentials: {target}")

            inventory["all"]["hosts"][target] = host_data
        return inventory

    def _run_ansible(
        self,
        playbook: List[Dict[str, Any]],
        inventory: Dict[str, Any],
        timeout: Optional[int] = None,
        extravars: Optional[Dict[str, Any]] = None,
        playbook_file: Optional[Path] = None,
    ) -> tuple[Any, List[Dict[str, Any]]]:
        """Execute Ansible playbook.

        Args:
            playbook: Playbook content (used when playbook_file is None).
            inventory: Ansible inventory dictionary.
            timeout: Timeout in seconds.
            extravars: Extra variables.
            playbook_file: Directly specify playbook file path, takes precedence over playbook parameter.

        Returns:
            tuple[Any, List[Dict[str, Any]]]: (ansible_runner result, events list).
        """
        timeout = min(timeout or self.config.default_timeout, self.config.max_timeout)
        task_id = str(uuid.uuid4())

        ansible_logger.log_execution_start(
            task_id=task_id,
            playbook=playbook,
            inventory=inventory,
            timeout=timeout,
            extravars=extravars,
        )

        start_time = time.time()

        base_dir = Path.cwd()
        tmp_dir = base_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=tmp_dir, prefix=f"ansible_{task_id}_"
        ) as tmpdir:
            tmpdir_path = Path(tmpdir)
            inventory_path = tmpdir_path / "inventory.json"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

            if playbook_file is not None:
                resolved_playbook_path = playbook_file
            else:
                resolved_playbook_path = tmpdir_path / "playbook.yml"
                playbook_content = yaml.dump(playbook, allow_unicode=True)
                resolved_playbook_path.write_text(playbook_content, encoding="utf-8")

            logger.debug(f"Executing playbook: {resolved_playbook_path}")
            logger.debug(f"Inventory: {inventory_path}")
            logger.info(f"Starting Ansible playbook execution: {resolved_playbook_path}")
            logger.info(f"Using inventory: {inventory_path}")
            logger.info(
                f"Target hosts: {list(inventory.get('all', {}).get('hosts', {}).keys())}"
            )

            result = ansible_runner.run(
                playbook=str(resolved_playbook_path),
                inventory=str(inventory_path),
                quiet=False,
                timeout=timeout,
                extravars=extravars,
            )

            events = list(result.events)

        logger.info(f"Ansible execution completed, return code: {result.rc}")
        logger.info(f"Ansible execution event count: {len(events)}")
        logger.info(f"Ansible execution statistics: {result.stats}")

        elapsed = time.time() - start_time

        # Only record key events to reduce log overhead, while calculating statistics simultaneously
        total_hosts = len(inventory.get("all", {}).get("hosts", {}))
        success_count = 0
        failed_count = 0
        unreachable_count = 0

        for event in events:
            event_type = event.get("event", "")
            if event_type in ["runner_on_failed", "runner_on_unreachable"]:
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task_name = event_data.get("task", "")
                res = event_data.get("res", {})

                ansible_logger.log_execution_event(
                    task_id=task_id,
                    event_type=event_type,
                    host=host,
                    task_name=task_name,
                    result=res,
                )

            # Calculate statistics simultaneously
            if event_type == "runner_on_ok":
                success_count += 1
            elif event_type == "runner_on_failed":
                failed_count += 1
            elif event_type == "runner_on_unreachable":
                unreachable_count += 1

        status = "success"
        if failed_count > 0 or unreachable_count > 0:
            if success_count > 0:
                status = "partial_success"
            else:
                status = "failed"

        ansible_logger.log_execution_result(
            task_id=task_id,
            status=status,
            summary={
                "total": total_hosts,
                "success": success_count,
                "failed": failed_count,
                "unreachable": unreachable_count,
            },
            elapsed=elapsed,
        )

        return result, events

    def _parse_wrapper_output(self, output: str) -> Dict[str, Any]:
        """Parse wrapper output.

        Args:
            output: Wrapper execution output.

        Returns:
            Dict[str, Any]: Parsed result, including stdout, stderr, rc, and elapsed.
        """
        result = {"stdout": "", "stderr": "", "rc": -1, "elapsed": "0s"}
        stdout_match = re.search(r"<<<STDOUT>>>(.*?)<<<STDERR>>>", output, re.DOTALL)
        if stdout_match:
            result["stdout"] = stdout_match.group(1).strip()
        rc_match = re.search(r"EXIT_CODE:(\d+)", output)
        if rc_match:
            result["rc"] = int(rc_match.group(1))
        elapsed_match = re.search(r"ELAPSED_TIME:([\d.]+)", output)
        if elapsed_match:
            result["elapsed"] = f"{elapsed_match.group(1)}s"
        return result

    def _test_connectivity(
        self,
        targets: List[str],
        inventory: Dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Dict[str, bool]:
        """Test host connectivity.

        Args:
            targets: List of target hosts.
            inventory: Ansible inventory.
            timeout: Timeout.

        Returns:
            Dictionary with host names as keys and connectivity status as values.
        """
        logger.info(f"Testing host connectivity: {targets}")

        playbook = [
            {
                "name": "Test connectivity",
                "hosts": "all",
                "gather_facts": False,
                "tasks": [
                    {
                        "name": "Ping test",
                        "ansible.builtin.raw": "echo 'connection_ok'",
                        "register": "ping_result",
                        "changed_when": False,
                    }
                ],
            }
        ]

        result, events = self._run_ansible(playbook, inventory, timeout)

        connectivity = {}
        for host in targets:
            connectivity[host] = False

        for event in events:
            event_type = event.get("event", "")
            if event_type == "runner_on_ok":
                host = event.get("event_data", {}).get("host", "")
                if host in connectivity:
                    connectivity[host] = True
                    logger.info(f"Host {host} connection test successful")
            elif event_type in ["runner_on_failed", "runner_on_unreachable"]:
                host = event.get("event_data", {}).get("host", "")
                if host in connectivity:
                    connectivity[host] = False
                    logger.warning(f"Host {host} connection test failed")

        return connectivity

    def _parse_result(
        self, result: Any, hosts: List[str], events: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        results = {}
        for host in hosts:
            results[host] = {"rc": -1, "stdout": "", "stderr": "", "elapsed": "0s"}

        # Process all events
        for event in events:
            event_type = event.get("event")
            event_data = event.get("event_data", {})
            host = event_data.get("host", "")

            if host not in results:
                continue

            if event_type == "runner_on_ok":
                res = event_data.get("res", {})
                stdout = res.get("stdout", "")
                if "<<<STDOUT>>>" in stdout:
                    parsed = self._parse_wrapper_output(stdout)
                    results[host] = parsed
                else:
                    results[host] = {
                        "rc": res.get("rc", 0),
                        "stdout": stdout,
                        "stderr": res.get("stderr", ""),
                        "elapsed": "0s",
                    }
            elif event_type in ["runner_on_failed", "runner_on_unreachable"]:
                res = event_data.get("res", {})
                results[host] = {
                    "rc": res.get("rc", result.rc),
                    "stdout": "",
                    "stderr": res.get("msg", str(event_data)),
                    "elapsed": "0s",
                    "error_type": (
                        "connection_error"
                        if "unreachable" in event_type
                        else "execution_error"
                    ),
                }

        return results

    def check_host_status(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        skip_lock: bool = False,
    ) -> Dict[str, Any]:
        logger.info(f"Checking host status: {targets}")
        logger.debug(
            f"Credential info: user={credentials.get('user') if credentials else None}, port={credentials.get('port') if credentials else None}"
        )

        # Check if hosts are busy (if not skipping lock)
        if not skip_lock:
            acquired, busy_hosts = self._acquire_hosts(targets)
            if not acquired:
                logger.warning(f"The following hosts are executing tasks, request rejected: {busy_hosts}")
                self._release_hosts(targets)
                return {
                    "task_id": task_id or str(uuid.uuid4()),
                    "status": "failed",
                    "summary": {
                        "total": len(targets),
                        "success": 0,
                        "error": len(targets),
                    },
                    "results": {
                        host: {
                            "error": f"Host {host} is executing a task, please try again later",
                            "error_type": "host_busy",
                        }
                        for host in targets
                    },
                }
            self._current_task_hosts = targets

        # Final inventory used
        final_inventory = None

        if credentials:
            logger.info("Building inventory with provided credentials...")
            # Directly use provided credentials to build inventory
            final_inventory = self._build_inventory(targets, credentials)

            # Update cached credential information for hosts with provided credentials
            for host in targets:
                update_result = self.inventory_manager.update_host_credentials(
                    host=host,
                    user=credentials.get("user"),
                    port=credentials.get("port"),
                    password=credentials.get("password"),
                    private_key=credentials.get("private_key"),
                )
                if update_result.get("status") != "success":
                    logger.warning(
                        f"Failed to update host credentials: {host}, error: {update_result.get('message')}"
                    )
                else:
                    logger.info(f"Host {host} credentials updated to cache")
        else:
            # No credentials provided, use cached inventory
            final_inventory = self._build_inventory(targets, credentials=None)

        # Ensure final_inventory is not None
        if final_inventory is None:
            final_inventory = self._build_inventory(targets, credentials=None)

        inventory = final_inventory
        logger.debug(f"Final inventory used: {inventory}")

        try:
            playbook = [
                {
                    "name": "Check host status",
                    "hosts": "all",
                    "gather_facts": False,
                    "serial": self.config.execution_serial,
                    "tasks": [
                        {
                            "name": "Detect architecture",
                            "ansible.builtin.raw": "uname -m",
                            "register": "arch_result",
                            "changed_when": False,
                        },
                        {
                            "name": "Detect distribution",
                            "ansible.builtin.raw": "cat /etc/os-release 2>/dev/null || echo 'ID=unknown'",
                            "register": "distro_result",
                            "changed_when": False,
                        },
                        {
                            "name": "Check Python3",
                            "ansible.builtin.raw": "if test -x /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3; then echo '/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3'; elif command -v python3 >/dev/null 2>&1; then command -v python3; else echo 'not_found'; fi",
                            "register": "python_check",
                            "changed_when": False,
                            "failed_when": False,
                        },
                        {
                            "name": "Get Python version",
                            "ansible.builtin.raw": "if test -x /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3; then /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3 --version 2>/dev/null; elif command -v python3 >/dev/null 2>&1; then python3 --version 2>/dev/null; else echo 'not_installed'; fi",
                            "register": "python_version",
                            "changed_when": False,
                            "failed_when": False,
                        },
                        {
                            "name": "Check tsc_tools",
                            "ansible.builtin.raw": "if test -x /home/tsc/tsc_tools/tsc && test -e /home/tsc/tsc_tools/release-note.md; then echo 'installed'; else echo 'not_installed'; fi",
                            "register": "tsc_tools_check",
                            "changed_when": False,
                            "failed_when": False,
                        },
                    ],
                }
            ]

            result, events = self._run_ansible(playbook, inventory, timeout)
            logger.debug(f"Ansible execution return code: {result.rc}")
            logger.debug(f"Ansible execution event count: {len(events)}")
            # Print detailed information for first few events
            for i, event in enumerate(events[:5]):
                logger.debug(
                    f"Event {i}: {event.get('event')}, host: {event.get('event_data', {}).get('host')}, task: {event.get('event_data', {}).get('task')}"
                )
            results = {}
            for host in targets:
                results[host] = {
                    "arch": "",
                    "arch_raw": "",
                    "distro": "",
                    "distro_raw": "",
                    "python_installed": False,
                    "python_version": "",
                    "python_path": "",
                    "tsc_python_installed": False,
                    "tsc_tools_installed": False,
                }
            for event in events:
                event_type = event.get("event", "")
                logger.debug(f"Processing event: {event_type}")
                if event_type == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    task = event_data.get("task", "")
                    res = event_data.get("res", {})
                    logger.debug(
                        f"Host {host} task '{task}' executed successfully, rc={res.get('rc')}"
                    )
                    if host in results:
                        if "Detect architecture" in task:
                            arch_raw = res.get("stdout", "").strip()
                            results[host]["arch_raw"] = arch_raw
                            results[host]["arch"] = self.config.normalize_architecture(
                                arch_raw
                            )
                            logger.info(
                                f"Host {host} architecture: raw={arch_raw}, normalized={results[host]['arch']}"
                            )
                        elif "Detect distribution" in task:
                            distro_raw = res.get("stdout", "").strip()
                            results[host]["distro_raw"] = distro_raw
                            id_match = re.search(r'ID="?([^"\s]+)"?', distro_raw)
                            if id_match:
                                distro_id = id_match.group(1)
                                normalized_distro = self.config.normalize_distribution(
                                    distro_id
                                )
                                results[host]["distro"] = normalized_distro
                                logger.info(
                                    f"Host {host} distribution: id={distro_id}, normalized={normalized_distro}"
                                )
                        elif "Check Python3" in task:
                            python_path = res.get("stdout", "").strip()
                            results[host]["python_installed"] = (
                                python_path and "not_found" not in python_path
                            )
                            if results[host]["python_installed"]:
                                results[host]["python_path"] = python_path
                                # Check if it is tsc_python
                                results[host]["tsc_python_installed"] = (
                                    "/tsc_tools/micromamba/envs/tsc_python/bin/python3"
                                    in python_path
                                )
                                self.inventory_manager.update_python_interpreter(
                                    host, python_path
                                )
                                logger.info(f"Host {host} Python path: {python_path}")
                                logger.info(
                                    f"Host {host} tsc_python: {'installed' if results[host]['tsc_python_installed'] else 'not installed'}"
                                )
                            else:
                                logger.info(f"Host {host} Python not installed")
                        elif "Get Python version" in task:
                            version = res.get("stdout", "").strip()
                            results[host]["python_version"] = (
                                version
                                if version and "not_installed" not in version
                                else ""
                            )
                            if results[host]["python_version"]:
                                logger.info(
                                    f"Host {host} Python version: {results[host]['python_version']}"
                                )
                        elif "Check tsc_tools" in task:
                            tsc_tools_output = res.get("stdout", "").strip()
                            results[host]["tsc_tools_installed"] = (
                                tsc_tools_output == "installed"
                            )
                            logger.info(
                                f"Host {host} tsc_tools: {'installed' if results[host]['tsc_tools_installed'] else 'not installed'}"
                            )
                elif event_type in ["runner_on_failed", "runner_on_unreachable"]:
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    task = event_data.get("task", "")
                    res = event_data.get("res", {})
                    error_msg = res.get("msg", "Unknown error")
                    error_type = (
                        "host_unreachable"
                        if "unreachable" in event_type
                        else "task_failed"
                    )
                    logger.warning(f"Host {host} task '{task}' execution failed: {error_msg}")
                    if host in results:
                        results[host]["error"] = error_msg
                        results[host]["error_task"] = task
                        results[host]["error_type"] = error_type
                        # Do not set python_installed and tsc_tools_installed to False as we cannot determine their status
                        logger.error(
                            f"Host {host} execution failed [{error_type}], task='{task}': {error_msg}"
                        )
            for host, host_result in results.items():
                logger.info(
                    f"Host {host} status summary: arch={host_result.get('arch')}, "
                    f"distro={host_result.get('distro')}, "
                    f"python_installed={host_result.get('python_installed')}, "
                    f"tsc_tools_installed={host_result.get('tsc_tools_installed')}"
                )

            final_task_id = task_id or str(uuid.uuid4())
            task_result_store.save_result(
                final_task_id, {"results": results, "elapsed": 0}
            )

            total = len(results)
            error_count = sum(1 for r in results.values() if r.get("error"))
            success_count = total - error_count

            return {
                "task_id": final_task_id,
                "status": "success" if error_count == 0 else "partial_success",
                "summary": {
                    "total": total,
                    "success": success_count,
                    "error": error_count,
                },
                "results": results,
            }
        finally:
            # Only release host locks if not skipping lock
            if not skip_lock:
                # Release host locks regardless of success or failure
                self._release_hosts(targets)
                self._current_task_hosts = []

    def _check_hosts_reachability(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]],
        timeout: Optional[int],
        detect_result: Optional[Dict[str, Any]] = None,
        skip_lock: bool = False,
    ) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
        """Check host reachability and return results

        Note: This method wraps check_host_status to extract unreachable host information

        Args:
            targets: List of target hosts
            credentials: SSH credentials
            timeout: Timeout in seconds
            detect_result: Existing detection results, use directly if available to avoid duplicate detection
            skip_lock: Whether to skip lock acquisition

        Returns:
            tuple: (unreachable host results dict, complete detection results)
        """
        if detect_result is None:
            detect_result = self.check_host_status(
                targets, credentials, timeout, skip_lock=skip_lock
            )
        logger.info(f"Environment detection results: {detect_result['results']}")
        results = {}
        for host, env_info in detect_result["results"].items():
            if env_info.get("error"):
                results[host] = {
                    "installed": False,
                    "skipped": False,
                    "message": f"Host unreachable: {env_info.get('error')}",
                    "error": env_info.get("error"),
                }
                logger.warning(f"Host {host} unreachable, skipping operation")
        return results, detect_result

    def install_python(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        detect_result: Optional[Dict[str, Any]] = None,
        skip_lock: bool = False,
    ) -> Dict[str, Any]:
        logger.info(f"Installing Python: {targets}")
        results, detect_result = self._check_hosts_reachability(
            targets,
            credentials,
            timeout,
            detect_result=detect_result,
            skip_lock=skip_lock,
        )

        hosts_need_install = [h for h in targets if h not in results]
        if not hosts_need_install:
            final_task_id = task_id or str(uuid.uuid4())
            total = len(results)
            error_count = len(results)
            return {
                "task_id": final_task_id,
                "status": "failed" if error_count == total else "partial_success",
                "summary": {
                    "total": total,
                    "installed": 0,
                    "skipped": 0,
                    "failed": error_count,
                },
                "results": results,
            }
        inventory = self._build_inventory(hosts_need_install, credentials)
        python_path = "/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3"
        idempotency_check_playbook = [
            {
                "name": "Check tsc_python installation",
                "hosts": "all",
                "gather_facts": False,
                "serial": self.config.execution_serial,
                "tasks": [
                    {
                        "name": "Check tsc_python",
                        "ansible.builtin.raw": f"if test -x {python_path}; then {python_path} --version 2>/dev/null && echo 'installed'; else echo 'not_installed'; fi",
                        "register": "python_check",
                        "changed_when": False,
                        "failed_when": False,
                    },
                ],
            }
        ]
        check_result, check_events = self._run_ansible(
            idempotency_check_playbook, inventory, timeout
        )
        hosts_need_install = []
        for event in check_events:
            if event.get("event") == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host in results:
                    continue
                if "Check tsc_python" in task:
                    stdout = res.get("stdout", "").strip()
                    if "installed" in stdout and "not_installed" not in stdout:
                        results[host] = {
                            "installed": True,
                            "skipped": True,
                            "message": "tsc_python already installed",
                            "python_version": stdout.replace("installed", "").strip(),
                            "python_path": python_path,
                        }
                        logger.info(f"Host {host} tsc_python already installed, skipping")
                    else:
                        hosts_need_install.append(host)
            elif event.get("event") in ["runner_on_failed", "runner_on_unreachable"]:
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                if host in results:
                    continue
                hosts_need_install.append(host)
        if not hosts_need_install:
            final_task_id = task_id or str(uuid.uuid4())
            total = len(results)
            skipped_count = sum(1 for r in results.values() if r.get("skipped"))
            installed_count = sum(1 for r in results.values() if r.get("installed"))
            error_count = total - installed_count - skipped_count
            return {
                "task_id": final_task_id,
                "status": "success" if error_count == 0 else "partial_success",
                "summary": {
                    "total": total,
                    "installed": installed_count,
                    "skipped": skipped_count,
                    "failed": error_count,
                },
                "results": results,
            }
        install_tasks = []
        for host in hosts_need_install:
            env_info = detect_result["results"][host]
            arch = env_info.get("arch", "x86_64")
            distro = env_info.get("distro", "redhat")
            if not arch or not distro:
                results[host] = {
                    "installed": False,
                    "skipped": False,
                    "message": f"Failed to get host architecture or distribution info: arch={arch}, distro={distro}",
                    "error": "environment_detection_failed",
                }
                logger.error(
                    f"Host {host} failed to get environment info: arch={arch}, distro={distro}"
                )
                continue
            install_url = self.config.get_python_install_url(distro, arch)
            logger.info(
                f"Host {host} installation info: arch={arch}, distro={distro}, url={install_url}"
            )
            install_tasks.append(
                {
                    "name": f"Install Python on {host}",
                    "ansible.builtin.raw": f"mkdir -p /tmp/tsc_python && curl -sSL {install_url} -o /tmp/tsc_python/install.sh && chmod +x /tmp/tsc_python/install.sh && /tmp/tsc_python/install.sh >/dev/null; rm -rf /tmp/tsc_python",
                    "when": f"inventory_hostname == '{host}'",
                    "register": f"install_result_{host.replace('.', '_')}",
                    "failed_when": False,
                }
            )
        playbook = [
            {
                "name": "Install Python",
                "hosts": "all",
                "gather_facts": False,
                "serial": self.config.execution_serial,
                "tasks": install_tasks
                + [
                    {
                        "name": "Verify Python installation",
                        "ansible.builtin.raw": "/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3 --version",
                        "register": "verify_result",
                        "failed_when": False,
                    },
                ],
            }
        ]
        result, install_events = self._run_ansible(playbook, inventory, timeout)
        install_output = {}
        for event in install_events:
            if event.get("event") == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host and "Install Python on" in task:
                    output = res.get("stdout", "") + res.get("stderr", "")
                    install_output[host] = output
            elif event.get("event") == "runner_on_failed":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host and "Install Python on" in task:
                    output = (
                        res.get("stdout", "")
                        + res.get("stderr", "")
                        + res.get("msg", "")
                    )
                    install_output[host] = output
        for host in hosts_need_install:
            host_result = {
                "installed": False,
                "message": "",
                "elapsed": "0s",
                "install_output": install_output.get(host, ""),
            }
            for event in install_events:
                if event.get("event") == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    if event_data.get("host") == host:
                        task = event_data.get("task", "")
                        if "Verify Python" in task:
                            res = event_data.get("res", {})
                            host_result["installed"] = res.get("rc", -1) == 0
                            host_result["python_version"] = res.get(
                                "stdout", ""
                            ).strip()
                            if host_result["installed"]:
                                python_path = "/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3"
                                self.inventory_manager.update_python_interpreter(
                                    host, python_path
                                )
                elif event.get("event") in [
                    "runner_on_failed",
                    "runner_on_unreachable",
                ]:
                    event_data = event.get("event_data", {})
                    if event_data.get("host") == host:
                        res = event_data.get("res", {})
                        task = event_data.get("task", "")
                        if "Install Python on" in task:
                            host_result["message"] = "Installation script execution failed"
                            host_result["install_output"] = (
                                res.get("stdout", "")
                                + res.get("stderr", "")
                                + res.get("msg", "")
                            )
                        else:
                            host_result["message"] = res.get("msg", "Installation failed")
                            host_result["install_output"] = res.get("msg", "")
            results[host] = host_result

        final_task_id = task_id or str(uuid.uuid4())
        task_result_store.save_result(final_task_id, {"results": results, "elapsed": 0})

        total = len(results)
        installed_count = sum(1 for r in results.values() if r.get("installed"))
        skipped_count = sum(1 for r in results.values() if r.get("skipped"))
        failed_count = total - installed_count - skipped_count

        return {
            "task_id": final_task_id,
            "status": "success" if failed_count == 0 else "partial_success",
            "summary": {
                "total": total,
                "installed": installed_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
            "results": results,
        }

    def install_tsc_tools(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        detect_result: Optional[Dict[str, Any]] = None,
        skip_lock: bool = False,
    ) -> Dict[str, Any]:
        logger.info(f"Installing tsc_tools: {targets}")
        results, detect_result = self._check_hosts_reachability(
            targets,
            credentials,
            timeout,
            detect_result=detect_result,
            skip_lock=skip_lock,
        )
        hosts_need_check = [h for h in targets if h not in results]
        if not hosts_need_check:
            final_task_id = task_id or str(uuid.uuid4())
            total = len(results)
            error_count = len(results)
            return {
                "task_id": final_task_id,
                "status": "failed" if error_count == total else "partial_success",
                "summary": {
                    "total": total,
                    "installed": 0,
                    "skipped": 0,
                    "failed": error_count,
                },
                "results": results,
            }
        install_path = self.config.tsc_tools_install_path
        inventory = self._build_inventory(hosts_need_check, credentials)
        playbook = [
            {
                "name": "Check tsc_tools installation",
                "hosts": "all",
                "gather_facts": False,
                "serial": self.config.execution_serial,
                "tasks": [
                    {
                        "name": "Check tsc_tools installation",
                        "ansible.builtin.raw": f"if test -d {install_path}/ && test -f {install_path}/release-note.md; then echo 'installed'; else echo 'not_installed'; fi",
                        "register": "install_check",
                        "changed_when": False,
                        "failed_when": False,
                    },
                ],
            }
        ]
        check_result, check_events = self._run_ansible(playbook, inventory, timeout)
        hosts_need_install = []
        for host in hosts_need_check:
            if host not in results:
                results[host] = {"installed": False, "skipped": False, "message": ""}
        for event in check_events:
            if event.get("event") == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host in results:
                    if "Check tsc_tools installation" in task:
                        stdout = res.get("stdout", "").strip()
                        if stdout == "installed":
                            results[host]["skipped"] = True
                            results[host]["message"] = "tsc_tools already installed"
        for host in hosts_need_check:
            if not results[host]["skipped"]:
                hosts_need_install.append(host)
        if not hosts_need_install:
            final_task_id = task_id or str(uuid.uuid4())
            total = len(results)
            skipped_count = sum(1 for r in results.values() if r.get("skipped"))
            installed_count = sum(1 for r in results.values() if r.get("installed"))
            error_count = total - installed_count - skipped_count
            return {
                "task_id": final_task_id,
                "status": "success" if error_count == 0 else "partial_success",
                "summary": {
                    "total": total,
                    "installed": installed_count,
                    "skipped": skipped_count,
                    "failed": error_count,
                },
                "results": results,
            }
        install_url = self.config.get_tsc_tools_install_url()
        logger.info(f"Installing tsc_tools, url={install_url}")
        install_playbook = [
            {
                "name": "Install tsc_tools",
                "hosts": "all",
                "gather_facts": False,
                "serial": self.config.execution_serial,
                "tasks": [
                    {
                        "name": "Download and install tsc_tools",
                        "ansible.builtin.raw": f"mkdir -p /tmp/tsc_tools && curl -sSL {install_url} -o /tmp/tsc_tools/install.sh && chmod +x /tmp/tsc_tools/install.sh && /tmp/tsc_tools/install.sh >/dev/null; rm -rf /tmp/tsc_tools",
                        "register": "install_result",
                        "failed_when": False,
                    },
                    {
                        "name": "Verify tsc_tools installation",
                        "ansible.builtin.raw": f"test -d {install_path}/ && test -f {install_path}/release-note.md && echo 'success' || echo 'failed'",
                        "register": "verify_result",
                        "failed_when": False,
                    },
                ],
            }
        ]
        install_inventory = self._build_inventory(hosts_need_install, credentials)
        result, install_events = self._run_ansible(
            install_playbook, install_inventory, timeout
        )
        install_output = {}
        for event in install_events:
            if event.get("event") == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host and "Download and install tsc_tools" in task:
                    output = res.get("stdout", "") + res.get("stderr", "")
                    install_output[host] = output
            elif event.get("event") == "runner_on_failed":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host and "Download and install tsc_tools" in task:
                    output = (
                        res.get("stdout", "")
                        + res.get("stderr", "")
                        + res.get("msg", "")
                    )
                    install_output[host] = output
        for host in hosts_need_install:
            host_result = {
                "installed": False,
                "message": "",
                "elapsed": "0s",
                "install_output": install_output.get(host, ""),
            }
            for event in install_events:
                if event.get("event") == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    if event_data.get("host") == host:
                        task = event_data.get("task", "")
                        res = event_data.get("res", {})
                        if "Verify tsc_tools" in task:
                            stdout = res.get("stdout", "").strip()
                            host_result["installed"] = stdout == "success"
                            if host_result["installed"]:
                                host_result["message"] = "tsc_tools installed successfully"
                            else:
                                host_result["message"] = "tsc_tools installation verification failed"
                elif event.get("event") in [
                    "runner_on_failed",
                    "runner_on_unreachable",
                ]:
                    event_data = event.get("event_data", {})
                    if event_data.get("host") == host:
                        res = event_data.get("res", {})
                        task = event_data.get("task", "")
                        if "Download and install tsc_tools" in task:
                            host_result["message"] = "Installation script execution failed"
                            host_result["install_output"] = (
                                res.get("stdout", "")
                                + res.get("stderr", "")
                                + res.get("msg", "")
                            )
                        else:
                            host_result["message"] = res.get("msg", "Installation failed")
                            host_result["install_output"] = res.get("msg", "")
            results[host] = host_result

        final_task_id = task_id or str(uuid.uuid4())
        task_result_store.save_result(final_task_id, {"results": results, "elapsed": 0})

        total = len(results)
        installed_count = sum(1 for r in results.values() if r.get("installed"))
        skipped_count = sum(1 for r in results.values() if r.get("skipped"))
        failed_count = total - installed_count - skipped_count

        return {
            "task_id": final_task_id,
            "status": "success" if failed_count == 0 else "partial_success",
            "summary": {
                "total": total,
                "installed": installed_count,
                "skipped": skipped_count,
                "failed": failed_count,
            },
            "results": results,
        }

    def ansible_copy(
        self,
        targets: List[str],
        src: str,
        dest: str,
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        detect_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Dispatching files: {targets}, src={src}, dest={dest}")
        src_path = Path(src)
        if not src_path.exists():
            logger.error(f"Local file not found: {src}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"Local file not found: {src}",
                        "elapsed": "0s",
                        "error_type": "file_not_found",
                    }
                    for host in targets
                },
            }
        # Acquire host locks
        acquired, busy_hosts = self._acquire_hosts(targets)
        if not acquired:
            logger.warning(f"The following hosts are executing tasks, request rejected: {busy_hosts}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"Host {host} is executing a task, please try again later",
                        "elapsed": "0s",
                        "error_type": "host_busy",
                    }
                    for host in targets
                },
            }
        self._current_task_hosts = targets
        try:
            if detect_result is None:
                detect_result = self.check_host_status(
                    targets, credentials, timeout, skip_lock=True
                )
            unreachable_hosts = [
                h for h, info in detect_result["results"].items() if info.get("error")
            ]
            if unreachable_hosts:
                logger.warning(f"The following hosts are unreachable: {unreachable_hosts}")
            reachable_hosts = [h for h in targets if h not in unreachable_hosts]
            if not reachable_hosts:
                return {
                    "task_id": task_id or str(uuid.uuid4()),
                    "status": "failed",
                    "summary": {
                        "total": len(targets),
                        "success": 0,
                        "failed": len(targets),
                    },
                    "results": {
                        host: {
                            "rc": -1,
                            "stdout": "",
                            "stderr": f"Host unreachable: {detect_result['results'][host].get('error')}",
                            "elapsed": "0s",
                            "error_type": "host_unreachable",
                        }
                        for host in targets
                    },
                }
            hosts_need_python = [
                h
                for h, info in detect_result["results"].items()
                if not info.get("error") and not info.get("python_installed")
            ]
            if hosts_need_python:
                logger.info(f"The following hosts need Python installed: {hosts_need_python}")
                install_result = self.install_python(
                    hosts_need_python,
                    credentials,
                    timeout=timeout,
                    detect_result=detect_result,
                    skip_lock=True,
                )
                failed_hosts = []
                for host, result in install_result["results"].items():
                    if not result.get("installed") and not result.get("skipped"):
                        logger.error(f"Python installation failed: {host}")
                        failed_hosts.append(host)
                if failed_hosts:
                    # Build error message with detailed installation failure reasons
                    results = {}
                    for host in targets:
                        error_msg = "Python installation failed, cannot dispatch files"
                        if host in install_result["results"]:
                            host_result = install_result["results"][host]
                            if "message" in host_result:
                                error_msg = f"Python installation failed: {host_result['message']}"
                            if (
                                "install_output" in host_result
                                and host_result["install_output"]
                            ):
                                error_msg += (
                                    f"\nInstallation output: {host_result['install_output']}"
                                )
                        results[host] = {
                            "rc": -1,
                            "stdout": "",
                            "stderr": error_msg,
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                    return {
                        "task_id": task_id or str(uuid.uuid4()),
                        "status": "failed",
                        "summary": {
                            "total": len(targets),
                            "success": 0,
                            "failed": len(targets),
                        },
                        "results": results,
                    }
            inventory = self._build_inventory(targets, credentials=credentials)
            playbook = [
                {
                    "name": "Dispatch file",
                    "hosts": "all",
                    "gather_facts": False,
                    "serial": self.config.execution_serial,
                    "tasks": [
                        {
                            "name": "Ensure destination directory exists",
                            "ansible.builtin.file": {
                                "path": str(Path(dest).parent),
                                "state": "directory",
                                "mode": "0755",
                            },
                        },
                        {
                            "name": "Copy file to destination",
                            "ansible.builtin.copy": {
                                "src": str(src_path),
                                "dest": dest,
                                "mode": "0644",
                            },
                            "register": "copy_result",
                        },
                        {
                            "name": "Verify file transfer",
                            "ansible.builtin.stat": {"path": dest},
                            "register": "verify_result",
                        },
                    ],
                }
            ]
            start_time = time.time()
            result, copy_events = self._run_ansible(playbook, inventory, timeout)
            elapsed = time.time() - start_time
            results: Dict[str, Dict[str, Any]] = {}
            for host in targets:
                results[host] = {
                    "rc": -1,
                    "stdout": "",
                    "stderr": "",
                    "elapsed": "0s",
                    "transferred": False,
                }
            for event in copy_events:
                if event.get("event") == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    task = event_data.get("task", "")
                    res = event_data.get("res", {})
                    if host in results:
                        if "Verify file transfer" in task:
                            stat_result = res.get("stat", {})
                            results[host]["transferred"] = stat_result.get(
                                "exists", False
                            )
                            results[host]["rc"] = (
                                0 if results[host]["transferred"] else -1
                            )
                            results[host]["stdout"] = (
                                f"File transferred to {dest}"
                                if results[host]["transferred"]
                                else "File transfer verification failed"
                            )
                        elif "Copy file to destination" in task:
                            results[host]["stdout"] = f"File copied successfully: {dest}"
                elif event.get("event") in [
                    "runner_on_failed",
                    "runner_on_unreachable",
                ]:
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    res = event_data.get("res", {})
                    if host in results:
                        results[host]["stderr"] = res.get("msg", "传输失败")
                        results[host]["error_type"] = (
                            "connection_error"
                            if "unreachable" in event.get("event", "")
                            else "transfer_error"
                        )

            final_task_id = task_id or str(uuid.uuid4())
            return self._build_summary_result(
                final_task_id, results, elapsed, "ansible_copy"
            )
        finally:
            # 释放主机锁
            self._release_hosts(targets)
            self._current_task_hosts = []

    def ansible_shell(
        self,
        targets: List[str],
        command: str,
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        detect_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"执行命令: {targets} - {command}")
        if self.config.is_high_risk_command(command):
            logger.warning(
                f"Blacklisted high-risk command '{command}' was intercepted. Logs have been recorded. Contact the administrator immediately. Model must stop subsequent operations."
            )
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"Blacklisted high-risk command {command} was intercepted. Logs have been recorded. Contact the administrator immediately. Model must stop subsequent operations.",
                        "elapsed": "0s",
                        "error_type": "high_risk_command",
                    }
                    for host in targets
                },
            }
        # 获取主机锁
        acquired, busy_hosts = self._acquire_hosts(targets)
        if not acquired:
            logger.warning(f"以下主机正在执行任务，拒绝请求: {busy_hosts}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"主机 {host} 正在执行任务，请稍后再试",
                        "elapsed": "0s",
                        "error_type": "host_busy",
                    }
                    for host in targets
                },
            }
        self._current_task_hosts = targets
        try:
            if detect_result is None:
                detect_result = self.check_host_status(
                    targets, credentials, timeout, skip_lock=True
                )
            unreachable_hosts = [
                h for h, info in detect_result["results"].items() if info.get("error")
            ]
            if unreachable_hosts:
                logger.warning(f"以下主机不可达: {unreachable_hosts}")
            reachable_hosts = [h for h in targets if h not in unreachable_hosts]
            if not reachable_hosts:
                return {
                    "task_id": str(uuid.uuid4()),
                    "status": "failed",
                    "summary": {
                        "total": len(targets),
                        "success": 0,
                        "failed": len(targets),
                    },
                    "results": {
                        host: {
                            "rc": -1,
                            "stdout": "",
                            "stderr": f"主机不可达: {detect_result['results'][host].get('error')}",
                            "elapsed": "0s",
                            "error_type": "host_unreachable",
                        }
                        for host in targets
                    },
                }
            hosts_need_python = [
                h
                for h, info in detect_result["results"].items()
                if not info.get("error") and not info.get("python_installed")
            ]
            if hosts_need_python:
                logger.info(f"以下主机需要安装 Python: {hosts_need_python}")
                install_result = self.install_python(
                    hosts_need_python,
                    credentials,
                    timeout=timeout,
                    detect_result=detect_result,
                    skip_lock=True,
                )
                failed_hosts = []
                for host, result in install_result["results"].items():
                    if not result.get("installed") and not result.get("skipped"):
                        logger.error(f"Python 安装失败: {host}")
                        failed_hosts.append(host)
                if failed_hosts:
                    # 构建包含详细安装失败原因的错误信息
                    results = {}
                    for host in targets:
                        error_msg = "Python 安装失败，无法执行命令"
                        if host in install_result["results"]:
                            host_result = install_result["results"][host]
                            if "message" in host_result:
                                error_msg = f"Python 安装失败: {host_result['message']}"
                            if (
                                "install_output" in host_result
                                and host_result["install_output"]
                            ):
                                error_msg += (
                                    f"\n安装输出: {host_result['install_output']}"
                                )
                        results[host] = {
                            "rc": -1,
                            "stdout": "",
                            "stderr": error_msg,
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                    return {
                        "task_id": task_id or str(uuid.uuid4()),
                        "status": "failed",
                        "summary": {
                            "total": len(targets),
                            "success": 0,
                            "failed": len(targets),
                        },
                        "results": results,
                    }

            inventory = self._build_inventory(targets, credentials=credentials)
            playbook = [
                {
                    "name": "Execute command",
                    "hosts": "all",
                    "gather_facts": False,
                    "serial": self.config.execution_serial,
                    "tasks": [
                        {
                            "name": "Execute command with wrapper",
                            "ansible.builtin.shell": {
                                "cmd": f"""
set -a
start_time=$(date +%s)
output=$({command} 2>&1)
rc=$?
end_time=$(date +%s)
elapsed=$(echo "$end_time - $start_time" | bc)
echo "<<<STDOUT>>>$output<<<STDERR>>>"
echo "EXIT_CODE:$rc"
echo "ELAPSED_TIME:$elapsed"
""",
                            },
                            "register": "command_result",
                        },
                    ],
                }
            ]
            start_time = time.time()
            result, events = self._run_ansible(playbook, inventory, timeout)
            elapsed = time.time() - start_time
            results = self._parse_result(result, targets, events)

            final_task_id = task_id or str(uuid.uuid4())
            return self._build_summary_result(
                final_task_id, results, elapsed, "ansible_shell"
            )
        finally:
            # 释放主机锁
            self._release_hosts(targets)
            self._current_task_hosts = []

    def _parse_playbook_metadata(self, playbook_path: Path) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "name": playbook_path.name,
            "path": str(playbook_path),
            "description": "",
            "author": "",
            "version": "",
            "tags": [],
            "parameters": [],
        }
        try:
            content = playbook_path.read_text(encoding="utf-8")

            json_metadata = self._extract_json_metadata(content)
            if json_metadata:
                metadata.update(json_metadata)
                return metadata

            in_description = False
            description_lines = []

            for line in content.split("\n"):
                stripped = line.strip()

                if stripped.startswith("---"):
                    break

                if not stripped.startswith("#"):
                    continue

                comment = stripped[1:].strip()

                if comment.startswith("@description:"):
                    metadata["description"] = comment.split(":", 1)[1].strip()
                elif comment.startswith("Description:"):
                    in_description = True
                    desc_content = comment.split(":", 1)[1].strip()
                    if desc_content:
                        description_lines.append(desc_content)
                elif in_description:
                    if comment and not comment.startswith(
                        (
                            "Author:",
                            "Version:",
                            "Tags:",
                            "Parameters:",
                            "Use Cases:",
                            "Example:",
                            "Notes:",
                            "Playbook:",
                        )
                    ):
                        description_lines.append(comment)
                    else:
                        in_description = False
                        if description_lines:
                            metadata["description"] = " ".join(description_lines)

                if comment.startswith("@author:"):
                    metadata["author"] = comment.split(":", 1)[1].strip()
                elif comment.startswith("Author:"):
                    metadata["author"] = comment.split(":", 1)[1].strip()

                if comment.startswith("@version:"):
                    metadata["version"] = comment.split(":", 1)[1].strip()
                elif comment.startswith("Version:"):
                    metadata["version"] = comment.split(":", 1)[1].strip()

                if comment.startswith("@tags:"):
                    tags_str = comment.split(":", 1)[1].strip()
                    metadata["tags"] = [
                        t.strip() for t in tags_str.split(",") if t.strip()
                    ]
                elif comment.startswith("Tags:"):
                    tags_str = comment.split(":", 1)[1].strip()
                    metadata["tags"] = [
                        t.strip() for t in tags_str.split(",") if t.strip()
                    ]

                if comment.startswith("@parameters:"):
                    params_str = comment.split(":", 1)[1].strip()
                    if params_str:
                        metadata["parameters"].append({"description": params_str})

            if description_lines and not metadata["description"]:
                metadata["description"] = " ".join(description_lines)

        except Exception as e:
            logger.exception(f"解析 playbook 元数据失败: {playbook_path}, 错误: {e}")
        return metadata

    def _extract_json_metadata(self, content: str) -> Optional[Dict[str, Any]]:
        """从注释中提取 JSON 格式的元数据"""
        try:
            json_lines = []
            in_meta = False

            for line in content.split("\n"):
                stripped = line.strip()

                if stripped.startswith("# @meta:"):
                    in_meta = True
                    json_start = stripped[8:].strip()
                    if json_start:
                        json_lines.append(json_start)
                    continue

                if in_meta:
                    if stripped.startswith("#"):
                        json_line = stripped[1:].strip()
                        json_lines.append(json_line)
                    elif stripped.startswith("---"):
                        break

            if not json_lines:
                return None

            json_str = "\n".join(json_lines)
            metadata = json.loads(json_str)

            if "parameters" in metadata:
                for param in metadata["parameters"]:
                    if "default" in param:
                        param["description"] = (
                            f"{param.get('description', '')} (default: {param['default']})"
                        )

            return metadata

        except json.JSONDecodeError as e:
            logger.exception(f"JSON 元数据解析失败: {e}")
            return None
        except Exception as e:
            logger.exception(f"提取 JSON 元数据失败: {e}")
            return None

    def list_playbooks(self) -> Dict[str, Any]:
        """列出所有可用的playbook文件

        Returns:
            Dict[str, Any]: 包含playbook列表的字典
        """
        playbooks_dir = self.config.playbooks_path
        if not playbooks_dir.exists():
            logger.warning(f"playbooks directory does not exist: {playbooks_dir}")
            return {"playbooks": []}
        playbooks = []
        # 同时遍历.yml和.yaml文件
        for pattern in ["*.yml", "*.yaml"]:
            for playbook_file in playbooks_dir.glob(pattern):
                if playbook_file.is_file():
                    metadata = self._parse_playbook_metadata(playbook_file)
                    playbooks.append(metadata)
        logger.info(f"找到 {len(playbooks)} 个 playbook 文件")
        return {"playbooks": playbooks}

    def run_playbook(
        self,
        playbook: str,
        targets: List[str],
        credentials: Optional[Dict[str, Any]] = None,
        extravars: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        detect_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"执行 playbook: {playbook}, 目标: {targets}")
        playbooks_dir = self.config.playbooks_path
        playbook_path = playbooks_dir / playbook
        if not playbook_path.exists():
            playbook_path = playbooks_dir / f"{playbook}.yml"
        if not playbook_path.exists():
            playbook_path = playbooks_dir / f"{playbook}.yaml"
        if not playbook_path.exists():
            logger.error(f"playbook 文件不存在: {playbook}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"playbook 文件不存在: {playbook}",
                        "elapsed": "0s",
                        "error_type": "playbook_not_found",
                    }
                    for host in targets
                },
            }
        acquired, busy_hosts = self._acquire_hosts(targets)
        if not acquired:
            logger.warning(f"以下主机正在执行任务，拒绝请求: {busy_hosts}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"主机 {host} 正在执行任务，请稍后再试",
                        "elapsed": "0s",
                        "error_type": "host_busy",
                    }
                    for host in targets
                },
            }
        self._current_task_hosts = targets
        try:
            if detect_result is None:
                detect_result = self.check_host_status(
                    targets, credentials, timeout, skip_lock=True
                )
            # 检查是否有不可达的主机
            unreachable_hosts = [
                h for h, info in detect_result["results"].items() if info.get("error")
            ]
            if unreachable_hosts:
                logger.warning(f"以下主机不可达: {unreachable_hosts}")
            reachable_hosts = [h for h in targets if h not in unreachable_hosts]
            if not reachable_hosts:
                return {
                    "task_id": task_id or str(uuid.uuid4()),
                    "status": "failed",
                    "summary": {
                        "total": len(targets),
                        "success": 0,
                        "failed": len(targets),
                    },
                    "results": {
                        host: {
                            "rc": -1,
                            "stdout": "",
                            "stderr": f"主机不可达: {detect_result['results'][host].get('error')}",
                            "elapsed": "0s",
                            "error_type": "host_unreachable",
                        }
                        for host in targets
                    },
                }
            # Check which hosts need Python installation (only check reachable hosts)
            hosts_need_python = [
                h
                for h, info in detect_result["results"].items()
                if h in reachable_hosts and not info.get("python_installed")
            ]
            if hosts_need_python:
                logger.info(f"以下主机需要安装 Python: {hosts_need_python}")
                install_result = self.install_python(
                    hosts_need_python,
                    credentials,
                    timeout=timeout,
                    detect_result=detect_result,
                    skip_lock=True,
                )
                failed_hosts = []
                for host, result in install_result["results"].items():
                    if not result.get("installed") and not result.get("skipped"):
                        logger.error(f"Python 安装失败: {host}")
                        failed_hosts.append(host)
                if failed_hosts:
                    # 构建包含详细安装失败原因的错误信息
                    results = {}
                    for host in targets:
                        error_msg = "Python 安装失败，无法执行 playbook"
                        if host in install_result["results"]:
                            host_result = install_result["results"][host]
                            if "message" in host_result:
                                error_msg = f"Python 安装失败: {host_result['message']}"
                            if (
                                "install_output" in host_result
                                and host_result["install_output"]
                            ):
                                error_msg += (
                                    f"\n安装输出: {host_result['install_output']}"
                                )
                        results[host] = {
                            "rc": -1,
                            "stdout": "",
                            "stderr": error_msg,
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                    return {
                        "task_id": str(uuid.uuid4()),
                        "status": "failed",
                        "summary": {
                            "total": len(targets),
                            "success": 0,
                            "failed": len(targets),
                        },
                        "results": results,
                    }
            inventory = self._build_inventory(targets, credentials=credentials)
            final_task_id = task_id or str(uuid.uuid4())

            start_time = time.time()
            result, run_events = self._run_ansible(
                playbook=[],
                inventory=inventory,
                timeout=timeout,
                extravars=extravars,
                playbook_file=playbook_path,
            )
            elapsed = time.time() - start_time

            results = self._parse_result(result, targets, run_events)

            for host in results:
                results[host]["elapsed"] = f"{elapsed:.2f}s"

            stats = {}
            for event in run_events:
                if event.get("event") == "playbook_on_stats":
                    stats = event.get("event_data", {})
                    break

            if stats:
                for host in targets:
                    host_stats = stats.get("processed", {})
                    if host in host_stats or host in stats.get("ok", {}):
                        if results[host]["rc"] == -1:
                            results[host]["rc"] = 0

            return self._build_summary_result(
                final_task_id, results, elapsed, "run_playbook"
            )
        finally:
            self._release_hosts(targets)
            self._current_task_hosts = []

    def ansible_fetch(
        self,
        targets: List[str],
        src: str,
        dest: str,
        credentials: Optional[Dict[str, Any]] = None,
        flat: bool = False,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
        detect_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"获取文件: {targets}, src={src}, dest={dest}")
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)
        # 获取主机锁
        acquired, busy_hosts = self._acquire_hosts(targets)
        if not acquired:
            logger.warning(f"以下主机正在执行任务，拒绝请求: {busy_hosts}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "dest": "",
                        "checksum": "",
                        "changed": False,
                        "stderr": f"主机 {host} 正在执行任务，请稍后再试",
                        "elapsed": "0s",
                        "error_type": "host_busy",
                    }
                    for host in targets
                },
            }
        self._current_task_hosts = targets
        try:
            if detect_result is None:
                detect_result = self.check_host_status(
                    targets, credentials, timeout, skip_lock=True
                )
            unreachable_hosts = [
                h for h, info in detect_result["results"].items() if info.get("error")
            ]
            if unreachable_hosts:
                logger.warning(f"以下主机不可达: {unreachable_hosts}")
            reachable_hosts = [h for h in targets if h not in unreachable_hosts]
            if not reachable_hosts:
                return {
                    "task_id": task_id or str(uuid.uuid4()),
                    "status": "failed",
                    "summary": {
                        "total": len(targets),
                        "success": 0,
                        "failed": len(targets),
                    },
                    "results": {
                        host: {
                            "rc": -1,
                            "dest": "",
                            "checksum": "",
                            "changed": False,
                            "stderr": f"主机不可达: {detect_result['results'][host].get('error')}",
                            "elapsed": "0s",
                            "error_type": "host_unreachable",
                        }
                        for host in targets
                    },
                }
            hosts_need_python = [
                h
                for h, info in detect_result["results"].items()
                if not info.get("error") and not info.get("python_installed")
            ]
            if hosts_need_python:
                logger.info(f"以下主机需要安装 Python: {hosts_need_python}")
                install_result = self.install_python(
                    hosts_need_python,
                    credentials,
                    timeout=timeout,
                    detect_result=detect_result,
                    skip_lock=True,
                )
                failed_hosts = []
                for host, result in install_result["results"].items():
                    if not result.get("installed") and not result.get("skipped"):
                        logger.error(f"Python 安装失败: {host}")
                        failed_hosts.append(host)
                if failed_hosts:
                    # 构建包含详细安装失败原因的错误信息
                    results = {}
                    for host in targets:
                        error_msg = "Python 安装失败，无法获取文件"
                        if host in install_result["results"]:
                            host_result = install_result["results"][host]
                            if "message" in host_result:
                                error_msg = f"Python 安装失败: {host_result['message']}"
                            if (
                                "install_output" in host_result
                                and host_result["install_output"]
                            ):
                                error_msg += (
                                    f"\n安装输出: {host_result['install_output']}"
                                )
                        results[host] = {
                            "rc": -1,
                            "dest": "",
                            "checksum": "",
                            "changed": False,
                            "stderr": error_msg,
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                    return {
                        "task_id": task_id or str(uuid.uuid4()),
                        "status": "failed",
                        "summary": {
                            "total": len(targets),
                            "success": 0,
                            "failed": len(targets),
                        },
                        "results": results,
                    }
            inventory = self._build_inventory(targets, credentials=credentials)
            playbook = [
                {
                    "name": "Fetch file",
                    "hosts": "all",
                    "gather_facts": False,
                    "serial": self.config.execution_serial,
                    "tasks": [
                        {
                            "name": "Fetch file from remote",
                            "ansible.builtin.fetch": {
                                "src": src,
                                "dest": dest,
                                "flat": flat,
                            },
                            "register": "fetch_result",
                        },
                    ],
                }
            ]
            start_time = time.time()
            result, fetch_events = self._run_ansible(playbook, inventory, timeout)
            elapsed = time.time() - start_time
            results = {}
            for host in targets:
                results[host] = {
                    "rc": -1,
                    "dest": "",
                    "checksum": "",
                    "changed": False,
                    "elapsed": "0s",
                }
            for event in fetch_events:
                if event.get("event") == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    task = event_data.get("task", "")
                    res = event_data.get("res", {})
                    if host in results and "Fetch file from remote" in task:
                        results[host]["rc"] = 0
                        results[host]["changed"] = res.get("changed", False)
                        results[host]["dest"] = res.get("dest", "")
                        results[host]["checksum"] = res.get("checksum", "")
                elif event.get("event") in [
                    "runner_on_failed",
                    "runner_on_unreachable",
                ]:
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    res = event_data.get("res", {})
                    if host in results:
                        results[host]["stderr"] = res.get("msg", "获取文件失败")
                        results[host]["error_type"] = (
                            "connection_error"
                            if "unreachable" in event.get("event", "")
                            else "fetch_error"
                        )

            final_task_id = task_id or str(uuid.uuid4())
            return self._build_summary_result(
                final_task_id, results, elapsed, "ansible_fetch"
            )
        finally:
            # 释放主机锁
            self._release_hosts(targets)
            self._current_task_hosts = []
