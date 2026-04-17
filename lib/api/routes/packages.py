from fastapi import APIRouter, Query, HTTPException, Response
from pathlib import Path
import os
from lib.config import settings
from lib.package_manager.manager import PackageManager

router = APIRouter(prefix="/api/v1/packages", tags=["packages"])

# 初始化包管理器
package_manager = PackageManager(settings.tsc_local_path)

@router.get("/download")
def download_package(
    response: Response,
    pkg_type: str = Query(..., description="Package type (e.g., tsc_tools, tsc_python)"),
    distro: str = Query(None, description="Distribution ID"),
    arch: str = Query(None, description="Architecture")
):
    """下载安装包"""
    try:
        package = package_manager.get_latest_package(pkg_type, distro, arch)
        
        # 设置响应头部
        response.headers["Content-Disposition"] = f"attachment; filename={package['filename']}"
        response.headers["Content-Type"] = "application/x-sh"
        
        # 读取文件内容
        content = package_manager.get_package_content(package["path"])
        return Response(content=content, media_type="application/x-sh")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 记录错误日志
        print(f"Error in download_package: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list/{pkg_type}")
def get_package_list(pkg_type: str):
    """获取包列表"""
    try:
        packages = package_manager.get_package_list(pkg_type)
        return {"packages": packages, "message": "Success"}
    except Exception as e:
        # 记录错误日志
        print(f"Error in get_package_list: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/refresh")
def refresh_cache():
    """刷新包缓存"""
    try:
        packages = package_manager.refresh_cache()
        return {"message": "Cache refreshed successfully", "packages": packages}
    except Exception as e:
        # 记录错误日志
        print(f"Error in refresh_cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
