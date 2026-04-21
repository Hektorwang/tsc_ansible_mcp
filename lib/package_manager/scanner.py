"""Package scanner module.

Provides functionality to scan installation packages and generate cache.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class PackageScanner:
    """Package scanner for scanning and caching installation packages.

    This class scans a directory for installation packages (.sh files),
    extracts metadata from filenames, and maintains a cache for quick lookup.

    Attributes:
        base_path: Base path to scan for packages.
        cache: Cached package information grouped by type.
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize package scanner.

        Args:
            base_path: Base path to scan for packages.
        """
        self.base_path = base_path
        self.cache: Dict[str, List[Dict[str, Any]]] = {}

    def scan_packages(self) -> Dict[str, List[Dict[str, Any]]]:
        """Scan all installation packages and generate cache.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Scanned packages grouped by type.
        """
        packages: Dict[str, List[Dict[str, Any]]] = {}

        # Scan all .sh package files
        for file in self.base_path.glob("*.sh"):
            # Extract package type (first field in filename)
            pkg_type = file.name.split("-")[0]
            if pkg_type not in packages:
                packages[pkg_type] = []

            # Store package info
            packages[pkg_type].append({"filename": file.name, "path": str(file)})

        self.cache = packages
        return packages

    def get_latest_package(
        self, pkg_type: str, distro: Optional[str] = None, arch: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the latest installation package matching criteria.

        Args:
            pkg_type: Package type (e.g., 'tsc_tools', 'tsc_python').
            distro: Distribution ID to match (optional).
            arch: Architecture to match (optional).

        Returns:
            Optional[Dict[str, Any]]: Package info if found, None otherwise.
        """
        if not self.cache:
            self.scan_packages()

        if pkg_type not in self.cache:
            return None

        packages = self.cache[pkg_type]
        if not packages:
            return None

        # Filter matching packages
        filtered: List[Dict[str, Any]] = []
        for pkg in packages:
            filename = pkg["filename"]

            # Check if matches distro and arch criteria
            if self._matches_criteria(filename, distro, arch):
                filtered.append(pkg)

        if not filtered:
            return None

        # Sort by version (version is typically in the second field)
        filtered.sort(key=lambda x: self._extract_version(x["filename"]), reverse=True)
        return filtered[0]

    def _matches_criteria(
        self, filename: str, distro: Optional[str] = None, arch: Optional[str] = None
    ) -> bool:
        """Check if filename matches distro and arch criteria.

        Args:
            filename: Package filename to check.
            distro: Distribution ID to match (optional).
            arch: Architecture to match (optional).

        Returns:
            bool: True if filename matches all specified criteria.
        """
        # Handle noarch case
        if "noarch" in filename:
            # noarch packages match any distro and any arch
            return True

        # Non-noarch packages need to match arch
        if arch and arch not in filename:
            return False

        # Check if distro matches
        if distro and distro not in filename:
            return False

        return True

    def _extract_version(self, filename: str) -> str:
        """Extract version number from filename.

        Args:
            filename: Package filename.

        Returns:
            str: Version string, empty string if not found.
        """
        parts = filename.split("-")
        if len(parts) >= 2:
            # Version is typically in the second field
            return parts[1]
        return ""

    def get_package_list(self, pkg_type: str) -> List[Dict[str, Any]]:
        """Get package list for a specific type.

        Args:
            pkg_type: Package type.

        Returns:
            List[Dict[str, Any]]: List of packages of the specified type.
        """
        if not self.cache:
            self.scan_packages()

        return self.cache.get(pkg_type, [])
