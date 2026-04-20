"""Package management API routes.

This module provides API endpoints for package download, listing, and cache management.
Note: These endpoints do not require authentication as they are intended for internal use
by target hosts during bootstrap process.
"""

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Response

from lib.config import settings
from lib.package_manager.manager import PackageManager
from lib.tsc_logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/v1/packages", tags=["packages"])

# Initialize package manager
package_manager = PackageManager(settings.tsc_local_path)


@router.get("/download")
def download_package(
    response: Response,
    pkg_type: str = Query(
        ..., description="Package type (e.g., tsc_tools, tsc_python)"
    ),
    distro: str = Query(None, description="Distribution ID"),
    arch: str = Query(None, description="Architecture"),
) -> Response:
    """Download installation package.

    Args:
        response: FastAPI response object.
        pkg_type: Package type (e.g., tsc_tools, tsc_python).
        distro: Distribution ID (optional).
        arch: Architecture (optional).

    Returns:
        Response: Package file content.

    Raises:
        HTTPException: If package not found or internal error occurs.
    """
    try:
        package = package_manager.get_latest_package(pkg_type, distro, arch)
        logger.info(
            f"Package download requested: type={pkg_type}, distro={distro}, arch={arch}, "
            f"filename={package['filename']}"
        )

        # Set response headers
        response.headers["Content-Disposition"] = (
            f"attachment; filename={package['filename']}"
        )
        response.headers["Content-Type"] = "application/x-sh"

        # Read file content
        content = package_manager.get_package_content(package["path"])
        return Response(content=content, media_type="application/x-sh")
    except ValueError as e:
        logger.warning(f"Package not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in download_package: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/list/{pkg_type}")
def get_package_list(pkg_type: str) -> Dict[str, Any]:
    """Get package list.

    Args:
        pkg_type: Package type.

    Returns:
        Dict[str, Any]: Package list and status message.

    Raises:
        HTTPException: If internal error occurs.
    """
    try:
        packages = package_manager.get_package_list(pkg_type)
        logger.info(f"Package list requested: type={pkg_type}, count={len(packages)}")
        return {"packages": packages, "message": "Success"}
    except Exception as e:
        logger.error(f"Error in get_package_list: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/refresh")
def refresh_cache() -> Dict[str, Any]:
    """Refresh package cache.

    Returns:
        Dict[str, Any]: Refresh result and package list.

    Raises:
        HTTPException: If internal error occurs.
    """
    try:
        packages = package_manager.refresh_cache()
        logger.info(f"Package cache refreshed: {len(packages)} package types")
        return {"message": "Cache refreshed successfully", "packages": packages}
    except Exception as e:
        logger.error(f"Error in refresh_cache: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
