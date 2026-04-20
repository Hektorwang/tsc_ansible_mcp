"""Package manager module.

Provides package management functionality including scanning, filtering,
and retrieving installation packages.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.package_manager.normalizer import PackageNormalizer
from lib.package_manager.scanner import PackageScanner


class PackageManager:
    """Package manager for handling installation packages.

    This class provides methods to scan, filter, and retrieve installation
    packages for tsc_tools and tsc_python.

    Attributes:
        base_path: Base path where packages are stored.
        scanner: Package scanner instance.
        normalizer: Package normalizer instance.
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize package manager.

        Args:
            base_path: Base path where packages are stored.
        """
        self.base_path = base_path
        self.scanner = PackageScanner(base_path)
        self.normalizer = PackageNormalizer()

    def get_latest_package(
        self, pkg_type: str, distro: Optional[str] = None, arch: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the latest installation package.

        Args:
            pkg_type: Package type (e.g., 'tsc_tools', 'tsc_python').
            distro: Distribution ID (optional, normalized internally).
            arch: Architecture (optional, normalized internally).

        Returns:
            Dict[str, Any]: Package information including filename and path.

        Raises:
            ValueError: If no matching package is found.
        """
        # Normalize distro and arch
        if distro:
            distro = self.normalizer.normalize_distro(distro)
        if arch:
            arch = self.normalizer.normalize_arch(arch)

        # Get package info
        package = self.scanner.get_latest_package(pkg_type, distro, arch)
        if not package:
            raise ValueError(
                f"Package not found: {pkg_type}, distro={distro}, arch={arch}"
            )

        return package

    def get_package_content(self, package_path: str) -> bytes:
        """Get package file content.

        Args:
            package_path: Path to the package file.

        Returns:
            bytes: Package file content.
        """
        with open(package_path, "rb") as f:
            return f.read()

    def refresh_cache(self) -> Dict[str, List[Dict[str, Any]]]:
        """Refresh package cache.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Scanned packages grouped by type.
        """
        return self.scanner.scan_packages()

    def get_package_list(self, pkg_type: str) -> List[Dict[str, Any]]:
        """Get package list for a specific type.

        Args:
            pkg_type: Package type.

        Returns:
            List[Dict[str, Any]]: List of packages of the specified type.
        """
        return self.scanner.get_package_list(pkg_type)
