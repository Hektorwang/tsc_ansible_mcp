"""
Configuration management module.

Load and manage tsc_ansible_mcp.toml configuration file.
"""

import re
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from lib.tsc_logger import get_logger

logger = get_logger()


class Config:
    """Configuration management class."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            base_dir = Path(__file__).parent.parent.resolve()
            config_path = base_dir / "etc" / "tsc_ansible_mcp.toml"
        self.path = Path(config_path)
        self._data = self._load()
        self._package_cache: Dict[str, Any] = {}
        self._last_modified = self.path.stat().st_mtime if self.path.exists() else 0
        self._scan_packages()  # Scan packages only once during initialization
        self._validate_config()

    def _check_for_updates(self) -> bool:
        """Check if configuration file has been updated."""
        if not self.path.exists():
            return False
        current_mtime = self.path.stat().st_mtime
        if current_mtime > self._last_modified:
            self._last_modified = current_mtime
            self._data = self._load()
            self._validate_config()
            return True
        return False

    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Validate timeout settings
        default_timeout = self.get("mcp.default_timeout", 600)
        max_timeout = self.get("mcp.max_timeout", 3600)
        if default_timeout > max_timeout:
            logger.warning(
                f"Default timeout ({default_timeout}) exceeds max timeout ({max_timeout}), "
                f"will use max timeout"
            )

        # Validate execution settings
        forks = self.get("execution.forks", 10)
        if forks < 1 or forks > 100:
            logger.warning(
                f"Forks value ({forks}) is out of reasonable range (1-100), "
                f"will use default value 10"
            )

        # Validate log level
        log_level = self.get("logging.level", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level not in valid_levels:
            logger.warning(f"Invalid log level ({log_level}), will use default INFO")

        # Validate auth settings
        auth_enabled = self.get("auth.enabled", False)
        if auth_enabled:
            # Check JWT secret key file
            secret_key_file = self.get("auth.jwt_secret_key_file", "etc/jwt_secret_key.txt")
            if not secret_key_file:
                logger.warning("JWT secret key file not configured, will use default path")

            # Check JWT issued tokens file
            issued_tokens_file = self.get("auth.jwt_issued_tokens_file", "etc/jwt_issued_tokens.json")
            if not issued_tokens_file:
                logger.warning("JWT issued tokens file not configured, will use default path")

            # Check tool permissions
            tool_permissions = self.get("auth.tool_permissions", {})
            if not tool_permissions:
                logger.warning("Tool permissions not configured, will use default permissions")
            else:
                # Validate each role has at least one permission
                for role, permissions in tool_permissions.items():
                    if not permissions:
                        logger.warning(f"Role '{role}' has no permissions configured")

        # Validate playbooks path
        playbooks_path = self.get("playbooks.path", "playbooks")
        if not playbooks_path:
            logger.warning("Playbooks path not configured, will use default 'playbooks'")

        # Validate tsc_repo settings
        base_url = self.get("tsc_repo.base_url")
        if base_url and not base_url.startswith(("http://", "https://")):
            logger.warning(f"Invalid base_url format: {base_url}, should start with http:// or https://")

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            with self.path.open("rb") as f:
                return tomllib.load(f)
        return self._defaults()

    def _defaults(self) -> Dict[str, Any]:
        return {
            "normalization": {
                "architecture": {
                    "aarch64": "aarch64",
                    "arm64": "aarch64",
                    "x86_64": "x86_64",
                    "amd64": "x86_64",
                },
                "distribution": {
                    "rhel": "RedHat",
                    "centos": "RedHat",
                    "almalinux": "RedHat",
                    "rocky": "RedHat",
                    "fedora": "RedHat",
                    "ubuntu": "Debian",
                    "debian": "Debian",
                    "linuxmint": "Debian",
                    "arch": "Arch",
                    "manjaro": "Arch",
                    "alpine": "Alpine",
                    "suse": "Suse",
                    "opensuse": "Suse",
                    "openeuler": "Euler",
                    "hce": "Euler",
                    "ningos": "Euler",
                },
            },
            "mcp": {
                "transport": "http",
                "host": "0.0.0.0",
                "port": 8500,
                "path": "/mcp",
                "default_timeout": 600,
                "max_timeout": 3600,
            },
            "tsc_repo": {
                "base_url": "http://192.168.19.22",
                "python_version": "0.9.5",
                "python_date": "20260330",
                "local_path": "/home/tsc/cicd/html",
                "tsc_tools_version": "2.0.3.beta10",
                "tsc_tools_date": "20260210",
                "tsc_tools_install_path": "/home/tsc/tsc_tools",
                "tsc_python_url_template": "/tsc_python-{version}-{distro}-{arch}-{date}.sh",
                "tsc_tools_url_template": "/tsc_tools-{version}-noarch-{date}.sh",
            },
            "execution": {
                "timeout": 300,
                "forks": 10,
                "serial": 10,
                "connection_timeout": 30,
                "max_failed_detail": 10,
                "max_output_length": 1000,
                "result_store_dir": "logs/task_results",
            },
            "playbooks": {
                "path": "playbooks",
            },
            "ssh": {
                "base_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ForwardX11=no -o GSSAPIAuthentication=no -o VerifyHostKeyDNS=no -o ConnectTimeout=30 -o ControlMaster=no -o ControlPath=none -o ControlPersist=0",
                "password_args": "-o PreferredAuthentications=password -o PubkeyAuthentication=no -o publickey=no",
            },
            "logging": {
                "dir": "logs",
                "level": "INFO",
                "ansible_execution_log": "ansible_execution.log",
                "ansible_execution_enabled": True,
                "ansible_execution_retention": "30 days",
                "ansible_execution_rotation": "50 MB",
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        # Check if configuration file has been updated
        self._check_for_updates()
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def normalization(self) -> Dict[str, Any]:
        return self.get("normalization", {})

    @property
    def architecture_mapping(self) -> Dict[str, str]:
        return self.normalization.get("architecture", {})

    @property
    def distribution_mapping(self) -> Dict[str, str]:
        return self.normalization.get("distribution", {})

    def normalize_architecture(self, arch: str) -> str:
        return self.architecture_mapping.get(arch, arch)

    def normalize_distribution(self, distro: str) -> str:
        lower_distro = distro.lower()
        if lower_distro in self.distribution_mapping:
            return self.distribution_mapping[lower_distro]
        for normalized in self.distribution_mapping.values():
            if normalized.lower() == lower_distro:
                return normalized
        return lower_distro

    @property
    def high_risk_commands(self) -> List[str]:
        return self.get("ansible.high_risk_commands", [])

    @property
    def mcp_settings(self) -> Dict[str, Any]:
        return self.get("mcp", {})

    @property
    def mcp_host(self) -> str:
        return self.mcp_settings.get("host", "0.0.0.0")

    @property
    def mcp_port(self) -> int:
        return self.mcp_settings.get("port", 8500)

    @property
    def mcp_path(self) -> str:
        return self.mcp_settings.get("path", "/mcp")

    @property
    def default_timeout(self) -> int:
        return self.mcp_settings.get("default_timeout", 600)

    @property
    def max_timeout(self) -> int:
        return self.mcp_settings.get("max_timeout", 3600)

    @property
    def mcp_version(self) -> str:
        return self.mcp_settings.get("mcp_version", "99.99.99")

    @property
    def nginx_settings(self) -> Dict[str, Any]:
        return self.get("tsc_repo", {})

    @property
    def nginx_base_url(self) -> str:
        return self.nginx_settings.get("base_url", "http://192.168.19.22")

    @property
    def nginx_python_version(self) -> str:
        return self.nginx_settings.get("python_version", "0.9.5")

    @property
    def nginx_python_date(self) -> str:
        return self.nginx_settings.get("python_date", "20260330")

    @property
    def nginx_local_path(self) -> str:
        return self.nginx_settings.get("local_path", "/home/tsc/cicd/html")

    @property
    def tsc_tools_version(self) -> str:
        return self.nginx_settings.get("tsc_tools_version", "2.0.3.beta10")

    @property
    def tsc_tools_date(self) -> str:
        return self.nginx_settings.get("tsc_tools_date", "20260210")

    @property
    def tsc_tools_install_path(self) -> str:
        return self.nginx_settings.get("tsc_tools_install_path", "/home/tsc/tsc_tools")

    @property
    def tsc_python_url_template(self) -> str:
        return self.nginx_settings.get(
            "tsc_python_url_template", "/tsc_python-{version}-{distro}-{arch}-{date}.sh"
        )

    @property
    def tsc_tools_url_template(self) -> str:
        return self.nginx_settings.get(
            "tsc_tools_url_template", "/tsc_tools-{version}-noarch-{date}.sh"
        )

    @property
    def tsc_local_path(self) -> Path:
        return Path(self.nginx_settings.get("local_path", "/home/tsc/cicd/html"))

    @property
    def execution_settings(self) -> Dict[str, Any]:
        return self.get("execution", {})

    @property
    def execution_timeout(self) -> int:
        return self.execution_settings.get("timeout", 300)

    @property
    def execution_forks(self) -> int:
        return self.execution_settings.get("forks", 10)

    @property
    def execution_serial(self) -> int:
        return self.execution_settings.get("serial", 10)

    @property
    def playbooks_settings(self) -> Dict[str, Any]:
        return self.get("playbooks", {})

    @property
    def playbooks_path(self) -> Path:
        base_dir = Path(__file__).parent.parent.resolve()
        return base_dir / self.playbooks_settings.get("path", "playbooks")

    @property
    def ssh_settings(self) -> Dict[str, Any]:
        return self.get("ssh", {})

    @property
    def ssh_base_args(self) -> str:
        return self.ssh_settings.get(
            "base_args",
            "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ForwardX11=no -o GSSAPIAuthentication=no -o VerifyHostKeyDNS=no",
        )

    @property
    def ssh_password_args(self) -> str:
        return self.ssh_settings.get(
            "password_args",
            "-o PreferredAuthentications=password -o PubkeyAuthentication=no",
        )

    def _get_cache_path(self) -> Path:
        base_dir = Path(__file__).parent.parent.resolve()
        logs_dir = base_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / "package_cache.yml"

    def _scan_packages(self) -> None:
        """Scan and cache available packages from local repository.
        
        This method runs only once during initialization to build package cache.
        """
        self._package_cache = {"tsc_python": {}, "tsc_tools": {}}
        local_path = Path(self.nginx_local_path)

        if not local_path.exists():
            self._save_cache()
            return

        python_pattern = re.compile(r"tsc_python-([\d.]+)-(\w+)-(\w+)-(\d+)\.sh")
        for f in local_path.glob("tsc_python-*.sh"):
            match = python_pattern.match(f.name)
            if match:
                version, distro, arch, date = match.groups()
                normalized_distro = self.normalize_distribution(distro)
                normalized_arch = self.normalize_architecture(arch)
                key = f"{normalized_distro}_{normalized_arch}"
                if key not in self._package_cache["tsc_python"]:
                    self._package_cache["tsc_python"][key] = {
                        "version": version,
                        "distro": normalized_distro,
                        "arch": normalized_arch,
                        "date": date,
                        "url": f"{self.nginx_base_url}/{f.name}",
                    }
                else:
                    existing = self._package_cache["tsc_python"][key]
                    if version > existing["version"] or (
                        version == existing["version"] and date > existing["date"]
                    ):
                        self._package_cache["tsc_python"][key] = {
                            "version": version,
                            "distro": normalized_distro,
                            "arch": normalized_arch,
                            "date": date,
                            "url": f"{self.nginx_base_url}/{f.name}",
                        }

        tools_pattern = re.compile(r"tsc_tools-([\w.]+)-noarch-(\d+)\.sh")
        for f in local_path.glob("tsc_tools-*.sh"):
            match = tools_pattern.match(f.name)
            if match:
                version, date = match.groups()
                key = "latest"
                if key not in self._package_cache["tsc_tools"]:
                    self._package_cache["tsc_tools"][key] = {
                        "version": version,
                        "date": date,
                        "url": f"{self.nginx_base_url}/{f.name}",
                    }
                else:
                    existing = self._package_cache["tsc_tools"][key]
                    if version > existing["version"] or (
                        version == existing["version"] and date > existing["date"]
                    ):
                        self._package_cache["tsc_tools"][key] = {
                            "version": version,
                            "date": date,
                            "url": f"{self.nginx_base_url}/{f.name}",
                        }

        self._save_cache()

    def _save_cache(self) -> None:
        cache_path = self._get_cache_path()
        with cache_path.open("w", encoding="utf-8") as f:
            yaml.dump(
                self._package_cache, f, default_flow_style=False, allow_unicode=True
            )

    def get_python_install_url(
        self,
        distro: str,
        arch: str,
        version: Optional[str] = None,
        date: Optional[str] = None,
    ) -> str:
        normalized_distro = self.normalize_distribution(distro)
        normalized_arch = self.normalize_architecture(arch)

        if version and date:
            url_path = self.tsc_python_url_template.format(
                version=version,
                date=date,
                distro=normalized_distro,
                arch=normalized_arch,
            )
            return f"{self.nginx_base_url}{url_path}"

        key = f"{normalized_distro}_{normalized_arch}"
        if key in self._package_cache.get("tsc_python", {}):
            return self._package_cache["tsc_python"][key]["url"]

        logger.warning(f"Package not found in cache: {key}, using default URL")
        logger.warning(
            f"Available cache keys: {list(self._package_cache.get('tsc_python', {}).keys())}"
        )

        url_path = self.tsc_python_url_template.format(
            version=self.nginx_python_version,
            date=self.nginx_python_date,
            distro=normalized_distro,
            arch=normalized_arch,
        )
        return f"{self.nginx_base_url}{url_path}"

    def get_tsc_tools_install_url(
        self, version: Optional[str] = None, date: Optional[str] = None
    ) -> str:
        if version and date:
            url_path = self.tsc_tools_url_template.format(version=version, date=date)
            return f"{self.nginx_base_url}{url_path}"

        if "latest" in self._package_cache.get("tsc_tools", {}):
            return self._package_cache["tsc_tools"]["latest"]["url"]

        url_path = self.tsc_tools_url_template.format(
            version=self.tsc_tools_version, date=self.tsc_tools_date
        )
        return f"{self.nginx_base_url}{url_path}"

    def is_high_risk_command(self, command: str) -> bool:
        """Check if command is a high-risk command

        Enhanced high-risk command checking supports:
        1. Detecting full paths (e.g., /usr/bin/rm)
        2. Detecting high-risk operations in command arguments
        3. Detecting complex commands with pipes and redirections
        4. Detecting common bypass techniques
        """
        command_lower = command.strip().lower()

        # List of common high-risk commands
        high_risk_cmds = [
            "rm",
            "unlink",
            "halt",
            "shutdown",
            "mkfs",
            "parted",
            "reboot",
            "poweroff",
            "init",
            "dd",
            "format",
            "shred",
        ]

        # Get high-risk command list from configuration
        config_risk_cmds = self.high_risk_commands
        if config_risk_cmds:
            high_risk_cmds.extend(config_risk_cmds)

        # Check if command contains high-risk commands
        for risk_cmd in high_risk_cmds:
            # Check full path (e.g., /usr/bin/rm)
            if f"/{risk_cmd}" in command_lower:
                return True

            # Check command part (e.g., rm)
            cmd_parts = command_lower.split()
            if risk_cmd in cmd_parts:
                return True

            # Check commands in pipes and redirections
            if "|" in command_lower or ">" in command_lower or "<" in command_lower:
                # Split command and check each part
                parts = (
                    command_lower.split("|")
                    + command_lower.split(">")
                    + command_lower.split("<")
                )
                for part in parts:
                    part_parts = part.strip().split()
                    if risk_cmd in part_parts:
                        return True

        return False

    @property
    def logging_settings(self) -> Dict[str, Any]:
        return self.get("logging", {})

    @property
    def logging_dir(self) -> str:
        return self.logging_settings.get("dir", "logs")

    @property
    def logging_level(self) -> str:
        return self.logging_settings.get("level", "INFO")

    @property
    def ansible_execution_log(self) -> str:
        return self.logging_settings.get(
            "ansible_execution_log", "ansible_execution.log"
        )

    @property
    def ansible_execution_enabled(self) -> bool:
        return self.logging_settings.get("ansible_execution_enabled", True)

    @property
    def ansible_execution_retention(self) -> str:
        return self.logging_settings.get("ansible_execution_retention", "30 days")

    @property
    def ansible_execution_rotation(self) -> str:
        return self.logging_settings.get("ansible_execution_rotation", "50 MB")

    @property
    def max_failed_detail(self) -> int:
        return self.execution_settings.get("max_failed_detail", 10)

    @property
    def max_output_length(self) -> int:
        return self.execution_settings.get("max_output_length", 1000)

    @property
    def result_store_dir(self) -> str:
        return self.execution_settings.get("result_store_dir", "logs/task_results")


# Create global configuration instance
settings = Config()
