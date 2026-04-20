"""Unit tests for Config module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.config import Config


class TestConfig:
    """Test cases for Config class."""

    def test_default_config(self):
        """Test default configuration values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.toml"
            config_path.write_text("", encoding="utf-8")

            with patch.object(Config, "_scan_packages"):
                config = Config(config_path)

            # Test default values
            assert config.default_timeout == 600
            assert config.max_timeout == 3600
            assert config.execution_forks == 10
            assert config.logging_level == "INFO"

    def test_normalize_architecture(self):
        """Test architecture normalization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.toml"
            config_path.write_text("", encoding="utf-8")

            with patch.object(Config, "_scan_packages"):
                config = Config(config_path)

            # Test architecture normalization
            assert config.normalize_architecture("aarch64") == "aarch64"
            assert config.normalize_architecture("arm64") == "aarch64"
            assert config.normalize_architecture("x86_64") == "x86_64"
            assert config.normalize_architecture("amd64") == "x86_64"

    def test_normalize_distribution(self):
        """Test distribution normalization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.toml"
            config_path.write_text("", encoding="utf-8")

            with patch.object(Config, "_scan_packages"):
                config = Config(config_path)

            # Test distribution normalization
            assert config.normalize_distribution("rhel") == "RedHat"
            assert config.normalize_distribution("centos") == "RedHat"
            assert config.normalize_distribution("ubuntu") == "Debian"
            assert config.normalize_distribution("debian") == "Debian"

    def test_is_high_risk_command(self):
        """Test high risk command detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.toml"
            config_path.write_text("", encoding="utf-8")

            with patch.object(Config, "_scan_packages"):
                config = Config(config_path)

            # Test high risk commands
            assert config.is_high_risk_command("rm -rf /") is True
            assert config.is_high_risk_command("shutdown now") is True
            assert config.is_high_risk_command("ls -la") is False
            assert config.is_high_risk_command("cat /etc/passwd") is False

    def test_custom_config(self):
        """Test custom configuration values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.toml"
            config_content = """
[mcp]
default_timeout = 300
max_timeout = 1800

[execution]
forks = 20

[logging]
level = "DEBUG"
"""
            config_path.write_text(config_content, encoding="utf-8")

            with patch.object(Config, "_scan_packages"):
                config = Config(config_path)

            # Test custom values
            assert config.default_timeout == 300
            assert config.max_timeout == 1800
            assert config.execution_forks == 20
            assert config.logging_level == "DEBUG"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
