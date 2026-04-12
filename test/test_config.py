import tempfile
import shutil
from pathlib import Path
import pytest
from lib.config import Config


class TestConfig:
    """测试 Config 类"""

    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_content = """
[normalization]
[normalization.architecture]
aarch64 = "aarch64"
arm64 = "aarch64"
x86_64 = "x86_64"
amd64 = "x86_64"
[normalization.distribution]
rhel = "RedHat"
centos = "RedHat"
ubuntu = "Debian"
debian = "Debian"

[mcp]
transport = "http"
host = "0.0.0.0"
port = 8500
path = "/mcp"
default_timeout = 600
max_timeout = 3600

[nginx]
base_url = "http://192.168.19.22"
python_version = "0.9.5"
python_date = "20260330"
local_path = "/home/tsc/cicd/html"

[execution]
timeout = 300
forks = 10
serial = 10

[playbooks]
path = "playbooks"
"""
        self.config_path = Path(self.temp_dir) / "tsc_ansible_mcp.toml"
        self.config_path.write_text(self.config_content, encoding="utf-8")
        self.config = Config(self.config_path)

    def teardown_method(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir)

    def test_get(self):
        """测试 get 方法"""
        assert self.config.get("mcp.host") == "0.0.0.0"
        assert self.config.get("mcp.port") == 8500
        assert self.config.get("non_existent_key") is None
        assert self.config.get("non_existent_key", "default") == "default"

    def test_normalize_architecture(self):
        """测试 normalize_architecture 方法"""
        assert self.config.normalize_architecture("aarch64") == "aarch64"
        assert self.config.normalize_architecture("arm64") == "aarch64"
        assert self.config.normalize_architecture("x86_64") == "x86_64"
        assert self.config.normalize_architecture("amd64") == "x86_64"
        assert self.config.normalize_architecture("unknown") == "unknown"

    def test_normalize_distribution(self):
        """测试 normalize_distribution 方法"""
        assert self.config.normalize_distribution("rhel") == "RedHat"
        assert self.config.normalize_distribution("centos") == "RedHat"
        assert self.config.normalize_distribution("ubuntu") == "Debian"
        assert self.config.normalize_distribution("debian") == "Debian"
        assert self.config.normalize_distribution("unknown") == "unknown"

    def test_get_python_install_url(self):
        """测试 get_python_install_url 方法"""
        url = self.config.get_python_install_url("RedHat", "x86_64")
        assert "http://192.168.19.22" in url
        assert "tsc_python" in url

    def test_get_tsc_tools_install_url(self):
        """测试 get_tsc_tools_install_url 方法"""
        url = self.config.get_tsc_tools_install_url()
        assert "http://192.168.19.22" in url
        assert "tsc_tools" in url

    def test_is_high_risk_command(self):
        """测试 is_high_risk_command 方法"""
        # 默认情况下，high_risk_commands 为空列表
        assert not self.config.is_high_risk_command("rm -rf /")
