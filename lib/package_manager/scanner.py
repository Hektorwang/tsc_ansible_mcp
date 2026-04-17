from pathlib import Path
import re
from typing import List, Dict, Optional

class PackageScanner:
    """包扫描器"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.cache = {}
    
    def scan_packages(self) -> Dict[str, List[Dict]]:
        """扫描所有安装包并生成缓存"""
        packages = {}
        
        # 扫描所有 .sh 包文件
        for file in self.base_path.glob("*.sh"):
            # 提取包类型（第一个字段）
            pkg_type = file.name.split('-')[0]
            if pkg_type not in packages:
                packages[pkg_type] = []
            
            # 存储包信息
            packages[pkg_type].append({
                "filename": file.name,
                "path": str(file)
            })
        
        self.cache = packages
        return packages
    
    def get_latest_package(self, pkg_type: str, distro: Optional[str] = None, arch: Optional[str] = None) -> Optional[Dict]:
        """获取最新的安装包"""
        if not self.cache:
            self.scan_packages()
        
        if pkg_type not in self.cache:
            return None
        
        packages = self.cache[pkg_type]
        if not packages:
            return None
        
        # 过滤匹配的包
        filtered = []
        for pkg in packages:
            filename = pkg["filename"]
            
            # 检查是否匹配 distro 和 arch
            if self._matches_criteria(filename, distro, arch):
                filtered.append(pkg)
        
        if not filtered:
            return None
        
        # 按版本排序（假设版本在文件名的第二个字段）
        filtered.sort(key=lambda x: self._extract_version(x["filename"]), reverse=True)
        return filtered[0]
    
    def _matches_criteria(self, filename: str, distro: Optional[str] = None, arch: Optional[str] = None) -> bool:
        """检查文件名是否匹配 distro 和 arch 条件"""
        # 处理 noarch 情况
        if "noarch" in filename:
            # noarch 包匹配任何 arch
            if distro:
                # 检查 distro 是否匹配
                return distro in filename or "noarch" in filename
            return True
        
        # 非 noarch 包需要匹配 arch
        if arch and arch not in filename:
            return False
        
        # 检查 distro 是否匹配
        if distro and distro not in filename:
            return False
        
        return True
    
    def _extract_version(self, filename: str) -> str:
        """提取版本号"""
        parts = filename.split('-')
        if len(parts) >= 2:
            # 版本号通常在第二个字段
            return parts[1]
        return ""
    
    def get_package_list(self, pkg_type: str) -> List[Dict]:
        """获取包列表"""
        if not self.cache:
            self.scan_packages()
        
        return self.cache.get(pkg_type, [])
