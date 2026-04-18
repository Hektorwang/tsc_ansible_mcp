from pathlib import Path

from .normalizer import PackageNormalizer
from .scanner import PackageScanner


class PackageManager:
    """包管理器"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.scanner = PackageScanner(base_path)
        self.normalizer = PackageNormalizer()

    def get_latest_package(
        self, pkg_type: str, distro: str = None, arch: str = None
    ) -> dict:
        """获取最新的安装包"""
        # 归一化处理
        if distro:
            distro = self.normalizer.normalize_distro(distro)
        if arch:
            arch = self.normalizer.normalize_arch(arch)

        # 获取包信息
        package = self.scanner.get_latest_package(pkg_type, distro, arch)
        if not package:
            raise ValueError(
                f"Package not found: {pkg_type}, distro={distro}, arch={arch}"
            )

        return package

    def get_package_content(self, package_path: str) -> bytes:
        """获取包内容"""
        with open(package_path, "rb") as f:
            return f.read()

    def refresh_cache(self):
        """刷新缓存"""
        return self.scanner.scan_packages()

    def get_package_list(self, pkg_type: str) -> list:
        """获取包列表"""
        return self.scanner.get_package_list(pkg_type)
