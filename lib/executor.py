"""
Ansible 执行引擎模块

提供远程命令执行、环境探测、Python 安装等功能
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
from lib.tsc_logger import get_logger
from lib.task_result_store import task_result_store

logger = get_logger()


class Executor:
    """Ansible 执行引擎"""

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
        """尝试获取主机的执行锁

        Args:
            hosts: 需要获取锁的主机列表

        Returns:
            tuple[bool, List[str]]: (success, busy_hosts) 是否成功获取，以及繁忙的主机列表
        """
        logger.debug(f"[LOCK] Attempting to acquire locks for hosts: {hosts}")
        with self._lock:
            logger.debug(f"[LOCK] _acquire_hosts called: hosts={hosts}, current_active={list(self._active_hosts)}")
            busy_hosts = [host for host in hosts if host in self._active_hosts]
            if busy_hosts:
                logger.warning(f"[LOCK] _acquire_hosts FAILED: hosts busy={busy_hosts}")
                logger.debug(f"[LOCK] Current active hosts: {list(self._active_hosts)}")
                return False, busy_hosts
            for host in hosts:
                self._active_hosts.add(host)
                logger.info(f"[LOCK] Acquired lock for host: {host}")
            logger.info(f"[LOCK] _acquire_hosts SUCCESS: hosts={hosts}, new_active={list(self._active_hosts)}")
            return True, []

    def _release_hosts(self, hosts: List[str]) -> None:
        """释放主机的执行锁

        Args:
            hosts: 需要释放锁的主机列表

        Returns:
            None
        """
        logger.debug(f"[LOCK] Attempting to release locks for hosts: {hosts}")
        with self._lock:
            logger.debug(f"[LOCK] _release_hosts called: hosts={hosts}, current_active={list(self._active_hosts)}")
            released_hosts = []
            skipped_hosts = []
            for host in hosts:
                if host in self._active_hosts:
                    self._active_hosts.remove(host)
                    released_hosts.append(host)
                    logger.info(f"[LOCK] Released host lock: {host}")
                else:
                    skipped_hosts.append(host)
                    logger.debug(f"[LOCK] Host {host} not in active hosts, skipping release")
            logger.info(f"[LOCK] _release_hosts done: released={released_hosts}, skipped={skipped_hosts}, remaining_active={list(self._active_hosts)}")

    def _install_signal_handlers(self):
        """安装信号处理器以确保锁被释放"""

        def signal_handler(signum, frame):
            logger.warning(f"[SIGNAL] 收到信号 {signum}，正在释放主机锁...")
            with self._lock:
                if self._current_task_hosts:
                    logger.warning(f"[SIGNAL] 释放锁: {self._current_task_hosts}")
                    for host in self._current_task_hosts:
                        if host in self._active_hosts:
                            self._active_hosts.remove(host)
                    self._current_task_hosts = []
            logger.warning("[SIGNAL] 主机锁已释放，程序即将退出")
            if signum == signal.SIGINT:
                raise KeyboardInterrupt("Ctrl+C interrupted")
            elif signum == signal.SIGTERM:
                raise SystemExit("SIGTERM received")

        self._original_signal_handler[signal.SIGINT] = signal.signal(signal.SIGINT, signal_handler)
        self._original_signal_handler[signal.SIGTERM] = signal.signal(signal.SIGTERM, signal_handler)

    def _restore_signal_handlers(self):
        """恢复原始信号处理器"""
        for sig, handler in self._original_signal_handler.items():
            signal.signal(sig, handler)

    def _build_summary_result(
        self,
        task_id: str,
        results: Dict[str, Dict[str, Any]],
        elapsed: float,
        task_type: str = "execution",
    ) -> Dict[str, Any]:
        """构建摘要返回结果

        Args:
            task_id: 任务 ID
            results: 所有主机的执行结果
            elapsed: 执行耗时
            task_type: 任务类型

        Returns:
            摘要结果字典
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

        message = f"执行完成，{failed_count} 台主机失败"
        if failed_count > 0:
            message += f"。使用 get_task_detail('{task_id}', host) 查看详情"

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
        """构建 Ansible inventory

        Args:
            targets: 目标主机列表
            credentials: LLM 提供的凭据信息

        Returns:
            Ansible inventory 字典
        """
        inventory: Dict[str, Any] = {"all": {"hosts": {}}}
        for target in targets:
            # 特殊处理 localhost，使用 local 连接而不是 SSH
            if target == "localhost":
                host_data: Dict[str, Any] = {
                    "ansible_connection": "local",
                    "ansible_python_interpreter": "/usr/bin/python3"
                }
                logger.debug(f"使用 local 连接处理 localhost")
            else:
                host_data: Dict[str, Any] = {
                    "ansible_host": target,
                    "ansible_ssh_common_args": self.config.ssh_base_args,
                }

                cached_host = self.inventory_manager.get_host(target)

                # 首先使用缓存的信息（如果有）
                if cached_host:
                    host_data.update(cached_host)
                    logger.debug(f"使用缓存的 inventory 信息: {target}")
                    if "ansible_python_interpreter" in cached_host:
                        logger.debug(
                            f"使用缓存的 Python 解释器: {cached_host['ansible_python_interpreter']}"
                        )

                # 如果提供了新的凭据，覆盖缓存的信息
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
                        logger.debug(f"使用提供的凭据: {target}, SSH参数: {host_data['ansible_ssh_common_args']}")
                    elif "private_key" in credentials:
                        host_data["ansible_ssh_private_key_file"] = credentials[
                            "private_key"
                        ]
                        host_data["ansible_ssh_common_args"] = self.config.ssh_base_args
                        logger.debug(f"使用提供的凭据: {target}, SSH参数: {host_data['ansible_ssh_common_args']}")
                    else:
                        logger.debug(f"使用提供的凭据: {target}")

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
        """执行 Ansible playbook

        Args:
            playbook: playbook 内容（当 playbook_file 为 None 时使用）
            inventory: Ansible inventory 字典
            timeout: 超时时间（秒）
            extravars: 额外变量
            playbook_file: 直接指定 playbook 文件路径，优先于 playbook 参数

        Returns:
            tuple[Any, List[Dict[str, Any]]]: (ansible_runner result, events 列表)
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

            logger.debug(f"执行 playbook: {resolved_playbook_path}")
            logger.debug(f"Inventory: {inventory_path}")
            logger.info(f"开始执行 Ansible playbook: {resolved_playbook_path}")
            logger.info(f"使用 inventory: {inventory_path}")
            logger.info(
                f"目标主机: {list(inventory.get('all', {}).get('hosts', {}).keys())}"
            )

            result = ansible_runner.run(
                playbook=str(resolved_playbook_path),
                inventory=str(inventory_path),
                quiet=False,
                timeout=timeout,
                extravars=extravars,
            )

            events = list(result.events)

        logger.info(f"Ansible 执行完成，返回码: {result.rc}")
        logger.info(f"Ansible 执行事件数量: {len(events)}")
        logger.info(f"Ansible 执行统计信息: {result.stats}")

        elapsed = time.time() - start_time

        # 只记录关键事件，减少日志开销，并同时计算统计信息
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

            # 同时计算统计信息
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
        """解析包装器输出

        Args:
            output: 包装器执行的输出

        Returns:
            Dict[str, Any]: 解析后的结果，包含stdout、stderr、rc和elapsed
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
        """测试主机连接性

        Args:
            targets: 目标主机列表
            inventory: Ansible inventory
            timeout: 超时时间

        Returns:
            字典，键为主机名，值为是否可连接
        """
        logger.info(f"测试主机连接性: {targets}")

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
                    logger.info(f"主机 {host} 连接测试成功")
            elif event_type in ["runner_on_failed", "runner_on_unreachable"]:
                host = event.get("event_data", {}).get("host", "")
                if host in connectivity:
                    connectivity[host] = False
                    logger.warning(f"主机 {host} 连接测试失败")

        return connectivity

    def _parse_result(
        self, result: Any, hosts: List[str], events: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        results = {}
        for host in hosts:
            results[host] = {"rc": -1, "stdout": "", "stderr": "", "elapsed": "0s"}

        # 处理所有事件
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
        logger.info(f"检查主机状态: {targets}")
        logger.debug(
            f"凭据信息: user={credentials.get('user') if credentials else None}, port={credentials.get('port') if credentials else None}"
        )

        # 检查主机是否繁忙（如果不跳过锁）
        if not skip_lock:
            acquired, busy_hosts = self._acquire_hosts(targets)
            if not acquired:
                logger.warning(f"以下主机正在执行任务，拒绝请求: {busy_hosts}")
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
                            "error": f"主机 {host} 正在执行任务，请稍后再试",
                            "error_type": "host_busy",
                        }
                        for host in targets
                    },
                }
            self._current_task_hosts = targets

        # 最终使用的 inventory
        final_inventory = None

        if credentials:
            logger.info("使用提供的凭据构建 inventory...")
            # 直接使用提供的凭据构建 inventory
            final_inventory = self._build_inventory(targets, credentials)
            
            # 对于提供了凭据的主机，更新缓存的凭据信息
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
                        f"更新主机凭据失败: {host}, 错误: {update_result.get('message')}"
                    )
                else:
                    logger.info(f"主机 {host} 凭据已更新到缓存")
        else:
            # 没有提供凭据，使用缓存的 inventory
            final_inventory = self._build_inventory(targets, credentials=None)

        # 确保 final_inventory 不为 None
        if final_inventory is None:
            final_inventory = self._build_inventory(targets, credentials=None)

        inventory = final_inventory
        logger.debug(f"最终使用的 inventory: {inventory}")

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
            logger.debug(f"Ansible 执行返回码: {result.rc}")
            logger.debug(f"Ansible 执行事件数量: {len(events)}")
            # 打印前几个事件的详细信息
            for i, event in enumerate(events[:5]):
                logger.debug(
                    f"事件 {i}: {event.get('event')}, 主机: {event.get('event_data', {}).get('host')}, 任务: {event.get('event_data', {}).get('task')}"
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
                logger.debug(f"处理事件: {event_type}")
                if event_type == "runner_on_ok":
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    task = event_data.get("task", "")
                    res = event_data.get("res", {})
                    logger.debug(
                        f"主机 {host} 任务 '{task}' 执行成功, rc={res.get('rc')}"
                    )
                    if host in results:
                        if "Detect architecture" in task:
                            arch_raw = res.get("stdout", "").strip()
                            results[host]["arch_raw"] = arch_raw
                            results[host]["arch"] = self.config.normalize_architecture(
                                arch_raw
                            )
                            logger.info(
                                f"主机 {host} 架构: raw={arch_raw}, normalized={results[host]['arch']}"
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
                                    f"主机 {host} 发行版: id={distro_id}, normalized={normalized_distro}"
                                )
                        elif "Check Python3" in task:
                            python_path = res.get("stdout", "").strip()
                            results[host]["python_installed"] = (
                                python_path and "not_found" not in python_path
                            )
                            if results[host]["python_installed"]:
                                results[host]["python_path"] = python_path
                                # 检查是否为 tsc_python
                                results[host]["tsc_python_installed"] = (
                                    "/tsc_tools/micromamba/envs/tsc_python/bin/python3"
                                    in python_path
                                )
                                self.inventory_manager.update_python_interpreter(
                                    host, python_path
                                )
                                logger.info(f"主机 {host} Python 路径: {python_path}")
                                logger.info(
                                    f"主机 {host} tsc_python: {'已安装' if results[host]['tsc_python_installed'] else '未安装'}"
                                )
                            else:
                                logger.info(f"主机 {host} Python 未安装")
                        elif "Get Python version" in task:
                            version = res.get("stdout", "").strip()
                            results[host]["python_version"] = (
                                version
                                if version and "not_installed" not in version
                                else ""
                            )
                            if results[host]["python_version"]:
                                logger.info(
                                    f"主机 {host} Python 版本: {results[host]['python_version']}"
                                )
                        elif "Check tsc_tools" in task:
                            tsc_tools_output = res.get("stdout", "").strip()
                            results[host]["tsc_tools_installed"] = (
                                tsc_tools_output == "installed"
                            )
                            logger.info(
                                f"主机 {host} tsc_tools: {'已安装' if results[host]['tsc_tools_installed'] else '未安装'}"
                            )
                elif event_type in ["runner_on_failed", "runner_on_unreachable"]:
                    event_data = event.get("event_data", {})
                    host = event_data.get("host", "")
                    task = event_data.get("task", "")
                    res = event_data.get("res", {})
                    error_msg = res.get("msg", "未知错误")
                    error_type = (
                        "host_unreachable"
                        if "unreachable" in event_type
                        else "task_failed"
                    )
                    logger.warning(f"主机 {host} 任务 '{task}' 执行失败: {error_msg}")
                    if host in results:
                        results[host]["error"] = error_msg
                        results[host]["error_task"] = task
                        results[host]["error_type"] = error_type
                        # 不要将python_installed和tsc_tools_installed设置为False，因为我们无法确定它们的状态
                        logger.error(
                            f"主机 {host} 执行失败 [{error_type}], task='{task}': {error_msg}"
                        )
            for host, host_result in results.items():
                logger.info(
                    f"主机 {host} 状态汇总: arch={host_result.get('arch')}, "
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
            # 只有在不跳过锁的情况下才释放主机锁
            if not skip_lock:
                # 无论执行成功或失败，都释放主机锁
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
        """检查主机可达性并返回结果

        注意：此方法是对check_host_status的包装，用于提取不可达主机信息

        Args:
            targets: 目标主机列表
            credentials: SSH 凭据
            timeout: 超时时间
            detect_result: 已有的探测结果，有值时直接使用，避免重复探测
            skip_lock: 是否跳过锁的获取

        Returns:
            tuple: (不可达主机结果字典, 完整探测结果)
        """
        if detect_result is None:
            detect_result = self.check_host_status(targets, credentials, timeout, skip_lock=skip_lock)
        logger.info(f"环境探测结果: {detect_result['results']}")
        results = {}
        for host, env_info in detect_result["results"].items():
            if env_info.get("error"):
                results[host] = {
                    "installed": False,
                    "skipped": False,
                    "message": f"主机不可达: {env_info.get('error')}",
                    "error": env_info.get("error"),
                }
                logger.warning(f"主机 {host} 不可达，跳过操作")
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
        logger.info(f"安装 Python: {targets}")
        results, detect_result = self._check_hosts_reachability(
            targets, credentials, timeout, detect_result=detect_result, skip_lock=skip_lock
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
                            "message": "tsc_python 已安装",
                            "python_version": stdout.replace("installed", "").strip(),
                            "python_path": python_path,
                        }
                        logger.info(f"主机 {host} tsc_python 已安装，跳过")
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
                    "message": f"无法获取主机架构或发行版信息: arch={arch}, distro={distro}",
                    "error": "environment_detection_failed",
                }
                logger.error(
                    f"主机 {host} 无法获取环境信息: arch={arch}, distro={distro}"
                )
                continue
            install_url = self.config.get_python_install_url(distro, arch)
            logger.info(
                f"主机 {host} 安装信息: arch={arch}, distro={distro}, url={install_url}"
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
                            host_result["message"] = "安装脚本执行失败"
                            host_result["install_output"] = (
                                res.get("stdout", "")
                                + res.get("stderr", "")
                                + res.get("msg", "")
                            )
                        else:
                            host_result["message"] = res.get("msg", "安装失败")
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
        logger.info(f"安装 tsc_tools: {targets}")
        results, detect_result = self._check_hosts_reachability(
            targets, credentials, timeout, detect_result=detect_result, skip_lock=skip_lock
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
                            results[host]["message"] = "tsc_tools 已安装"
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
        logger.info(f"安装 tsc_tools, url={install_url}")
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
                                host_result["message"] = "tsc_tools 安装成功"
                            else:
                                host_result["message"] = "tsc_tools 安装验证失败"
                elif event.get("event") in [
                    "runner_on_failed",
                    "runner_on_unreachable",
                ]:
                    event_data = event.get("event_data", {})
                    if event_data.get("host") == host:
                        res = event_data.get("res", {})
                        task = event_data.get("task", "")
                        if "Download and install tsc_tools" in task:
                            host_result["message"] = "安装脚本执行失败"
                            host_result["install_output"] = (
                                res.get("stdout", "")
                                + res.get("stderr", "")
                                + res.get("msg", "")
                            )
                        else:
                            host_result["message"] = res.get("msg", "安装失败")
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
        logger.info(f"分发文件: {targets}, src={src}, dest={dest}")
        src_path = Path(src)
        if not src_path.exists():
            logger.error(f"本地文件不存在: {src}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"本地文件不存在: {src}",
                        "elapsed": "0s",
                        "error_type": "file_not_found",
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
                detect_result = self.check_host_status(targets, credentials, timeout, skip_lock=True)
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
                        error_msg = "Python 安装失败，无法分发文件"
                        if host in install_result["results"]:
                            host_result = install_result["results"][host]
                            if "message" in host_result:
                                error_msg = f"Python 安装失败: {host_result['message']}"
                            if "install_output" in host_result and host_result["install_output"]:
                                error_msg += f"\n安装输出: {host_result['install_output']}"
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
                            results[host]["transferred"] = stat_result.get("exists", False)
                            results[host]["rc"] = 0 if results[host]["transferred"] else -1
                            results[host]["stdout"] = (
                                f"文件已传输到 {dest}"
                                if results[host]["transferred"]
                                else "文件传输验证失败"
                            )
                        elif "Copy file to destination" in task:
                            results[host]["stdout"] = f"文件复制成功: {dest}"
                elif event.get("event") in ["runner_on_failed", "runner_on_unreachable"]:
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
                detect_result = self.check_host_status(targets, credentials, timeout, skip_lock=True)
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
                            if "install_output" in host_result and host_result["install_output"]:
                                error_msg += f"\n安装输出: {host_result['install_output']}"
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
            logger.warning(f"playbooks 目录不存在: {playbooks_dir}")
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
                detect_result = self.check_host_status(targets, credentials, timeout, skip_lock=True)
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
            # 检查哪些主机需要安装Python（只检查可到达的主机）
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
                            if "install_output" in host_result and host_result["install_output"]:
                                error_msg += f"\n安装输出: {host_result['install_output']}"
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
                detect_result = self.check_host_status(targets, credentials, timeout, skip_lock=True)
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
                            if "install_output" in host_result and host_result["install_output"]:
                                error_msg += f"\n安装输出: {host_result['install_output']}"
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
                elif event.get("event") in ["runner_on_failed", "runner_on_unreachable"]:
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
