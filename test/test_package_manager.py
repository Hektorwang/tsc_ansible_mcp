"""Unit tests for Package Manager module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.package_manager.manager import PackageManager
from lib.package_manager.scanner import PackageScanner


class TestPackageScanner:
    """Test cases for PackageScanner class."""

    def test_scan_packages(self):
        """Test package scanning functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create test package files
            (base_path / "tsc_tools-2.0.3-noarch-20260210.sh").touch()
            (base_path / "tsc_python-0.9.5-RedHat-x86_64-20260330.sh").touch()
            (base_path / "tsc_python-0.9.5-Debian-x86_64-20260330.sh").touch()

            scanner = PackageScanner(base_path)
            packages = scanner.scan_packages()

            # Verify scan results
            assert "tsc_tools" in packages
            assert "tsc_python" in packages
            assert len(packages["tsc_tools"]) == 1
            assert len(packages["tsc_python"]) == 2

    def test_get_latest_package(self):
        """Test getting latest package."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create test package files
            (base_path / "tsc_tools-2.0.3-noarch-20260210.sh").touch()
            (base_path / "tsc_python-0.9.5-RedHat-x86_64-20260330.sh").touch()

            scanner = PackageScanner(base_path)

            # Test getting latest package
            package = scanner.get_latest_package("tsc_tools")
            assert package is not None
            assert "tsc_tools" in package["filename"]

            # Test with distro and arch
            package = scanner.get_latest_package("tsc_python", distro="RedHat", arch="x86_64")
            assert package is not None
            assert "RedHat" in package["filename"]
            assert "x86_64" in package["filename"]

    def test_get_package_list(self):
        """Test getting package list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create test package files
            (base_path / "tsc_tools-2.0.3-noarch-20260210.sh").touch()
            (base_path / "tsc_tools-2.0.4-noarch-20260301.sh").touch()

            scanner = PackageScanner(base_path)
            packages = scanner.get_package_list("tsc_tools")

            assert len(packages) == 2

    def test_noarch_package_matching(self):
        """Test noarch package matching logic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create noarch package
            (base_path / "tsc_tools-2.0.3-noarch-20260210.sh").touch()

            scanner = PackageScanner(base_path)

            # Noarch should match any arch
            package = scanner.get_latest_package("tsc_tools", arch="x86_64")
            assert package is not None

            package = scanner.get_latest_package("tsc_tools", arch="aarch64")
            assert package is not None


class TestPackageManager:
    """Test cases for PackageManager class."""

    def test_get_latest_package(self):
        """Test getting latest package through manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create test package files
            (base_path / "tsc_tools-2.0.3-noarch-20260210.sh").touch()

            manager = PackageManager(base_path)
            package = manager.get_latest_package("tsc_tools")

            assert package is not None
            assert "filename" in package
            assert "path" in package

    def test_get_package_content(self):
        """Test reading package content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            # Create test package file with content
            test_file = base_path / "tsc_tools-2.0.3-noarch-20260210.sh"
            test_content = b"#!/bin/bash\necho 'test'"
            test_file.write_bytes(test_content)

            manager = PackageManager(base_path)
            content = manager.get_package_content(str(test_file))

            assert content == test_content

    def test_package_not_found(self):
        """Test error handling when package not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)

            manager = PackageManager(base_path)

            with pytest.raises(ValueError, match="Package not found"):
                manager.get_latest_package("nonexistent_package")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
