"""
Ansible 执行引擎模块

提供远程命令执行、环境探测、Python 安装等功能
"""

import json
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import ansible_runner
import yaml

from lib.ansible_logger import ansible_logger
from lib.config import Config
from lib.inventory_manager import InventoryManager
from lib.logger import get_logger
from lib.task_result_store import task_result_store

logger = get_logger()


class Executor:
    """Ansible 执行引擎"""

    def __init__(self, config: Config, inventory_manager: InventoryManager):
        self.config = config
        self.inventory_manager = inventory_manager
        ansible_logger._setup_from_config(config)

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
        use_cached: bool = False,
    ) -> Dict[str, Any]:
        """构建 Ansible inventory

        Args:
            targets: 目标主机列表
            credentials: LLM 提供的凭据信息
            use_cached: 是否强制使用缓存的 inventory（用于 fallback）

        Returns:
            Ansible inventory 字典
        """
        inventory: Dict[str, Any] = {"all": {"hosts": {}}}
        for target in targets:
            host_data: Dict[str, Any] = {
                "ansible_host": target,
                "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PreferredAuthentications=password -o PubkeyAuthentication=no",
            }

            cached_host = self.inventory_manager.get_host(target)

            if use_cached and cached_host:
                host_data.update(cached_host)
                logger.info(f"使用缓存的 inventory 信息: {target}")
                if "ansible_python_interpreter" in cached_host:
                    logger.info(
                        f"使用缓存的 Python 解释器: {cached_host['ansible_python_interpreter']}"
                    )
            elif credentials:
                if "user" in credentials:
                    host_data["ansible_user"] = credentials["user"]
                if "port" in credentials:
                    host_data["ansible_port"] = credentials["port"]
                if "password" in credentials:
                    host_data["ansible_password"] = credentials["password"]
                elif "private_key" in credentials:
                    host_data["ansible_ssh_private_key_file"] = credentials[
                        "private_key"
                    ]
                    host_data["ansible_ssh_common_args"] = (
                        "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
                    )
                logger.debug(f"使用 LLM 提供的凭据: {target}")
            elif cached_host:
                host_data.update(cached_host)
                logger.debug(f"使用缓存的 inventory 信息（无新凭据）: {target}")

            inventory["all"]["hosts"][target] = host_data
        return inventory

    def _run_ansible(
        self,
        playbook: List[Dict[str, Any]],
        inventory: Dict[str, Any],
        timeout: Optional[int] = None,
        extravars: Optional[Dict[str, Any]] = None,
    ) -> Any:
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

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            playbook_path = tmpdir_path / "playbook.yml"
            inventory_path = tmpdir_path / "inventory.json"
            playbook_path.write_text(json.dumps(playbook), encoding="utf-8")
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            logger.debug(f"执行 playbook: {playbook_path}")
            logger.debug(f"Inventory: {inventory_path}")
            result = ansible_runner.run(
                playbook=str(playbook_path),
                inventory=str(inventory_path),
                quiet=True,
                timeout=timeout,
                extravars=extravars,
            )

        elapsed = time.time() - start_time

        for event in result.events:
            event_type = event.get("event", "")
            event_data = event.get("event_data", {})

            if event_type in [
                "runner_on_ok",
                "runner_on_failed",
                "runner_on_unreachable",
            ]:
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

        total_hosts = len(inventory.get("all", {}).get("hosts", {}))
        success_count = 0
        failed_count = 0
        unreachable_count = 0

        for event in result.events:
            event_type = event.get("event", "")
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

        return result

    def _parse_wrapper_output(self, output: str) -> Dict[str, Any]:
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

        result = self._run_ansible(playbook, inventory, timeout)

        connectivity = {}
        for host in targets:
            connectivity[host] = False

        for event in result.events:
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

    def _parse_result(self, result: Any, hosts: List[str]) -> Dict[str, Dict[str, Any]]:
        results = {}
        for host in hosts:
            results[host] = {"rc": -1, "stdout": "", "stderr": "", "elapsed": "0s"}
        if result.rc == 0:
            for event in result.events:
                if event.get("event") == "runner_on_ok":
                    host = event.get("event_data", {}).get("host", "")
                    res = event.get("event_data", {}).get("res", {})
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
        else:
            for event in result.events:
                if event.get("event") in ["runner_on_failed", "runner_on_unreachable"]:
                    host = event.get("event_data", {}).get("host", "")
                    res = event.get("event_data", {}).get("res", {})
                    results[host] = {
                        "rc": res.get("rc", result.rc),
                        "stdout": "",
                        "stderr": res.get("msg", str(event.get("event_data", {}))),
                        "elapsed": "0s",
                        "error_type": (
                            "connection_error"
                            if "unreachable" in event.get("event", "")
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
    ) -> Dict[str, Any]:
        logger.info(f"检查主机状态: {targets}")
        logger.debug(
            f"凭据信息: user={credentials.get('user') if credentials else None}, port={credentials.get('port') if credentials else None}"
        )

        install_path = self.config.tsc_tools_install_path

        if credentials:
            logger.info("使用 LLM 提供的凭据测试连接...")
            inventory = self._build_inventory(targets, credentials, use_cached=False)
            test_result = self._test_connectivity(targets, inventory, timeout)

            failed_hosts = [
                host for host, success in test_result.items() if not success
            ]
            success_hosts = [host for host, success in test_result.items() if success]

            if failed_hosts:
                logger.warning(f"LLM 凭据连接失败的主机: {failed_hosts}")
                cached_inventory = self._build_inventory(
                    targets, credentials=None, use_cached=True
                )
                cached_test_result = self._test_connectivity(
                    targets, cached_inventory, timeout
                )

                for host in failed_hosts:
                    if cached_test_result.get(host, False):
                        logger.info(f"主机 {host} 使用缓存凭据连接成功，将使用缓存信息")
                    else:
                        logger.warning(f"主机 {host} 缓存凭据也连接失败")

            for host in success_hosts:
                self.inventory_manager.update_host_credentials(
                    host=host,
                    user=credentials.get("user"),
                    port=credentials.get("port"),
                    password=credentials.get("password"),
                    private_key=credentials.get("private_key"),
                )
                logger.info(f"主机 {host} 验证成功，已更新 inventory")

        inventory = self._build_inventory(targets, credentials=None, use_cached=True)
        logger.debug(f"最终使用的 inventory: {inventory}")

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
                        "ansible.builtin.raw": f"if test -x {install_path}/micromamba/envs/tsc_python/bin/python3; then echo '{install_path}/micromamba/envs/tsc_python/bin/python3'; elif command -v python3 >/dev/null 2>&1; then command -v python3; else echo 'not_found'; fi",
                        "register": "python_check",
                        "changed_when": False,
                        "failed_when": False,
                    },
                    {
                        "name": "Get Python version",
                        "ansible.builtin.raw": f"if test -x {install_path}/micromamba/envs/tsc_python/bin/python3; then {install_path}/micromamba/envs/tsc_python/bin/python3 --version 2>/dev/null; elif command -v python3 >/dev/null 2>&1; then python3 --version 2>/dev/null; else echo 'not_installed'; fi",
                        "register": "python_version",
                        "changed_when": False,
                        "failed_when": False,
                    },
                    {
                        "name": "Check tsc_tools",
                        "ansible.builtin.raw": f"test -d {install_path}/ && test -f {install_path}/release-note.md && echo 'installed' || echo 'not_installed'",
                        "register": "tsc_tools_check",
                        "changed_when": False,
                        "failed_when": False,
                    },
                ],
            }
        ]
        result = self._run_ansible(playbook, inventory, timeout)
        logger.debug(f"Ansible 执行返回码: {result.rc}")
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
        for event in result.events:
            event_type = event.get("event", "")
            logger.debug(f"处理事件: {event_type}")
            if event_type == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                logger.debug(f"主机 {host} 任务 '{task}' 执行成功, rc={res.get('rc')}")
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
                            tsc_python_path = (
                                f"{install_path}/micromamba/envs/tsc_python/bin/python3"
                            )
                            results[host]["tsc_python_installed"] = (
                                python_path == tsc_python_path
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
                logger.warning(f"主机 {host} 任务 '{task}' 执行失败: {error_msg}")
                if host in results:
                    results[host]["error"] = "主机不可达"
                    results[host]["tsc_tools_installed"] = False
                    results[host]["python_installed"] = False
                    logger.error(f"主机 {host} 不可达，跳过后续检查")
        for host, host_result in results.items():
            logger.info(
                f"主机 {host} 状态汇总: arch={host_result.get('arch')}, "
                f"distro={host_result.get('distro')}, "
                f"python_installed={host_result.get('python_installed')}, "
                f"tsc_tools_installed={host_result.get('tsc_tools_installed')}"
            )

        final_task_id = task_id or str(uuid.uuid4())
        task_result_store.save_result(final_task_id, {"results": results, "elapsed": 0})

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

    def install_python(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]] = None,
        version: Optional[str] = None,
        date: Optional[str] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"安装 Python: {targets}")
        detect_result = self.check_host_status(targets, credentials, timeout)
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
                logger.warning(f"主机 {host} 不可达，跳过安装")
            elif env_info.get("tsc_python_installed"):
                results[host] = {
                    "installed": False,
                    "skipped": True,
                    "message": "tsc_python 已安装",
                    "python_version": env_info.get("python_version", ""),
                    "python_path": env_info.get("python_path", ""),
                }
                logger.info(f"主机 {host} tsc_python 已安装，跳过")
        hosts_need_install = [h for h in targets if h not in results]
        if not hosts_need_install:
            final_task_id = task_id or str(uuid.uuid4())
            return {"task_id": final_task_id, "results": results}
        inventory = self._build_inventory(hosts_need_install, credentials)
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
            install_url = self.config.get_python_install_url(
                distro, arch, version, date
            )
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
        result = self._run_ansible(playbook, inventory, timeout)
        install_output = {}
        for event in result.events:
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
            for event in result.events:
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
        version: Optional[str] = None,
        date: Optional[str] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"安装 tsc_tools: {targets}")
        detect_result = self.check_host_status(targets, credentials, timeout)
        logger.info(f"环境探测结果: {detect_result['results']}")
        pre_check_results = {}
        hosts_need_check = []
        for host, env_info in detect_result["results"].items():
            if env_info.get("error"):
                pre_check_results[host] = {
                    "installed": False,
                    "skipped": False,
                    "message": f"主机不可达: {env_info.get('error')}",
                    "error": env_info.get("error"),
                }
                logger.warning(f"主机 {host} 不可达，跳过安装")
            else:
                hosts_need_check.append(host)
        if not hosts_need_check:
            final_task_id = task_id or str(uuid.uuid4())
            return {"task_id": final_task_id, "results": pre_check_results}
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
                        "name": "Check tsc_tools directory",
                        "ansible.builtin.raw": f"test -d {install_path}/ && echo 'installed' || echo 'not_installed'",
                        "register": "dir_check",
                        "changed_when": False,
                        "failed_when": False,
                    },
                    {
                        "name": "Check release-note.md",
                        "ansible.builtin.raw": f"test -f {install_path}/release-note.md && echo 'installed' || echo 'not_installed'",
                        "register": "note_check",
                        "changed_when": False,
                        "failed_when": False,
                    },
                ],
            }
        ]
        check_result = self._run_ansible(playbook, inventory, timeout)
        results = dict(pre_check_results)
        hosts_need_install = []
        for host in hosts_need_check:
            results[host] = {"installed": False, "skipped": False, "message": ""}
        for event in check_result.events:
            if event.get("event") == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                task = event_data.get("task", "")
                res = event_data.get("res", {})
                if host in results:
                    if "Check tsc_tools directory" in task:
                        stdout = res.get("stdout", "").strip()
                        if stdout == "installed":
                            results[host]["skipped"] = True
                            results[host]["message"] = "tsc_tools 已安装"
                    elif "Check release-note.md" in task:
                        stdout = res.get("stdout", "").strip()
                        if stdout == "installed":
                            results[host]["skipped"] = True
                            results[host]["message"] = "tsc_tools 已安装"
        for host in hosts_need_check:
            if not results[host]["skipped"]:
                hosts_need_install.append(host)
        if not hosts_need_install:
            final_task_id = task_id or str(uuid.uuid4())
            return {"task_id": final_task_id, "results": results}
        install_url = self.config.get_tsc_tools_install_url(version, date)
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
        result = self._run_ansible(install_playbook, install_inventory, timeout)
        install_output = {}
        for event in result.events:
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
            for event in result.events:
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

    def dispatch_file(
        self,
        targets: List[str],
        src: str,
        dest: str,
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
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
        detect_result = self.check_host_status(targets, credentials, timeout)
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
                hosts_need_python, credentials, timeout=timeout
            )
            failed_hosts = []
            for host, result in install_result["results"].items():
                if not result.get("installed") and not result.get("skipped"):
                    logger.error(f"Python 安装失败: {host}")
                    failed_hosts.append(host)
            if failed_hosts:
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
                            "stderr": "Python 安装失败，无法分发文件",
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                        for host in targets
                    },
                }
        inventory = self._build_inventory(targets, credentials=None, use_cached=True)
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
        result = self._run_ansible(playbook, inventory, timeout)
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
        for event in result.events:
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
            final_task_id, results, elapsed, "dispatch_file"
        )

    def ansible_shell(
        self,
        targets: List[str],
        command: str,
        credentials: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"执行命令: {targets} - {command}")
        if self.config.is_high_risk_command(command):
            logger.warning(f"高危命令被拦截, 日志已记录, 请联系管理员: {command}")
            return {
                "task_id": task_id or str(uuid.uuid4()),
                "status": "failed",
                "results": {
                    host: {
                        "rc": -1,
                        "stdout": "",
                        "stderr": f"高危命令被拦截, 日志已记录, 请联系管理员: {command}",
                        "elapsed": "0s",
                        "error_type": "high_risk_command",
                    }
                    for host in targets
                },
            }
        detect_result = self.check_host_status(targets, credentials, timeout)
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
                hosts_need_python, credentials, timeout=timeout
            )
            failed_hosts = []
            for host, result in install_result["results"].items():
                if not result.get("installed") and not result.get("skipped"):
                    logger.error(f"Python 安装失败: {host}")
                    failed_hosts.append(host)
            if failed_hosts:
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
                            "stderr": f"Python 安装失败，无法执行命令",
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                        for host in targets
                    },
                }

        inventory = self._build_inventory(targets, credentials=None, use_cached=True)
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
output=$(eval '{command}' 2>&1)
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
        result = self._run_ansible(playbook, inventory, timeout)
        elapsed = time.time() - start_time
        results = self._parse_result(result, targets)

        final_task_id = task_id or str(uuid.uuid4())
        return self._build_summary_result(
            final_task_id, results, elapsed, "ansible_shell"
        )

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
                    pass
                elif comment.startswith("Parameters:"):
                    pass
                else:
                    param_line = comment.lstrip("-").strip()
                    if param_line and "(" in param_line and ":" in param_line:
                        param_match = re.match(r"(\w+)\s*\((\w+)\):\s*(.+)", param_line)
                        if param_match:
                            metadata["parameters"].append(
                                {
                                    "name": param_match.group(1),
                                    "type": param_match.group(2),
                                    "description": param_match.group(3),
                                }
                            )
                    elif param_line and ":" in param_line:
                        parts = param_line.split(":", 1)
                        if len(parts) == 2:
                            param_name = parts[0].strip()
                            param_desc = parts[1].strip()
                            if param_name and not param_name.startswith(
                                (
                                    "Use",
                                    "Example",
                                    "Notes",
                                    "Playbook",
                                    "Description",
                                    "Author",
                                    "Version",
                                    "Tags",
                                )
                            ):
                                metadata["parameters"].append(
                                    {
                                        "name": param_name,
                                        "description": param_desc,
                                    }
                                )

            if description_lines and not metadata["description"]:
                metadata["description"] = " ".join(description_lines)

        except Exception as e:
            logger.warning(f"解析 playbook 元数据失败: {playbook_path}, 错误: {e}")
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
            logger.debug(f"JSON 元数据解析失败: {e}")
            return None
        except Exception as e:
            logger.debug(f"提取 JSON 元数据失败: {e}")
            return None

    def list_playbooks(self) -> Dict[str, Any]:
        playbooks_dir = self.config.playbooks_path
        if not playbooks_dir.exists():
            logger.warning(f"playbooks 目录不存在: {playbooks_dir}")
            return {"playbooks": []}
        playbooks = []
        for playbook_file in playbooks_dir.glob("*.yml"):
            if playbook_file.is_file():
                metadata = self._parse_playbook_metadata(playbook_file)
                playbooks.append(metadata)
        for playbook_file in playbooks_dir.glob("*.yaml"):
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
        detect_result = self.check_host_status(targets, credentials, timeout)
        hosts_need_python = [
            h
            for h, info in detect_result["results"].items()
            if not info.get("python_installed")
        ]
        if hosts_need_python:
            logger.info(f"以下主机需要安装 Python: {hosts_need_python}")
            install_result = self.install_python(
                hosts_need_python, credentials, timeout=timeout
            )
            failed_hosts = []
            for host, result in install_result["results"].items():
                if not result.get("installed") and not result.get("skipped"):
                    logger.error(f"Python 安装失败: {host}")
                    failed_hosts.append(host)
            if failed_hosts:
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
                            "stderr": "Python 安装失败，无法执行 playbook",
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                        for host in targets
                    },
                }
        inventory = self._build_inventory(targets, credentials=None, use_cached=True)
        timeout = min(timeout or self.config.default_timeout, self.config.max_timeout)
        start_time = time.time()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            inventory_path = tmpdir_path / "inventory.json"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            logger.debug(f"执行 playbook: {playbook_path}")
            logger.debug(f"Inventory: {inventory_path}")
            result = ansible_runner.run(
                playbook=str(playbook_path),
                inventory=str(inventory_path),
                quiet=True,
                timeout=timeout,
                extravars=extravars,
            )
        elapsed = time.time() - start_time
        results: Dict[str, Dict[str, Any]] = {}
        for host in targets:
            results[host] = {
                "rc": -1,
                "stdout": "",
                "stderr": "",
                "elapsed": f"{elapsed:.2f}s",
            }
        stats = {}
        for event in result.events:
            if event.get("event") == "playbook_on_stats":
                stats = event.get("event_data", {})
            elif event.get("event") == "runner_on_ok":
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                res = event_data.get("res", {})
                if host in results:
                    results[host]["rc"] = 0
                    if "stdout" in res:
                        results[host]["stdout"] += res.get("stdout", "") + "\n"
                    if "msg" in res:
                        results[host]["stdout"] += str(res.get("msg", "")) + "\n"
            elif event.get("event") in ["runner_on_failed", "runner_on_unreachable"]:
                event_data = event.get("event_data", {})
                host = event_data.get("host", "")
                res = event_data.get("res", {})
                if host in results:
                    results[host]["rc"] = res.get("rc", 2)
                    results[host]["stderr"] = res.get(
                        "msg", res.get("stderr", "任务执行失败")
                    )
        if stats:
            for host in targets:
                host_stats = stats.get("processed", {})
                if host in host_stats or host in stats.get("ok", {}):
                    if results[host]["rc"] == -1:
                        results[host]["rc"] = 0

        final_task_id = task_id or str(uuid.uuid4())
        return self._build_summary_result(
            final_task_id, results, elapsed, "run_playbook"
        )

    def ansible_fetch(
        self,
        targets: List[str],
        src: str,
        dest: str,
        credentials: Optional[Dict[str, Any]] = None,
        flat: bool = False,
        timeout: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"获取文件: {targets}, src={src}, dest={dest}")
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)
        detect_result = self.check_host_status(targets, credentials, timeout)
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
                hosts_need_python, credentials, timeout=timeout
            )
            failed_hosts = []
            for host, result in install_result["results"].items():
                if not result.get("installed") and not result.get("skipped"):
                    logger.error(f"Python 安装失败: {host}")
                    failed_hosts.append(host)
            if failed_hosts:
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
                            "stderr": "Python 安装失败，无法获取文件",
                            "elapsed": "0s",
                            "error_type": "python_install_failed",
                        }
                        for host in targets
                    },
                }
        inventory = self._build_inventory(targets, credentials=None, use_cached=True)
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
        result = self._run_ansible(playbook, inventory, timeout)
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
        for event in result.events:
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

    ansible_copy = dispatch_file
