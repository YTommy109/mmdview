# backend/routers/update.py
"""アップデート確認・ダウンロード・インストールの API。"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.paths import TEMPLATES_DIR
from backend.services.update_installer import install_update
from backend.services.update_service import update_service
from backend.version import __version__ as _CURRENT_VERSION

router = APIRouter(prefix="/api/update", tags=["update"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/dialog", response_class=HTMLResponse)
def update_dialog(request: Request) -> HTMLResponse:
    result = update_service.check_update()
    return templates.TemplateResponse(
        request,
        "update_dialog.html",
        {
            "available": result["available"],
            "latest_version": result["version"],
            "current_version": _CURRENT_VERSION,
            "download_url": result["download_url"],
        },
    )


@router.get("/check", response_class=HTMLResponse)
def check_update(request: Request) -> HTMLResponse:
    result = update_service.check_update()
    if not result["available"]:
        return templates.TemplateResponse(request, "partials/update_idle.html", {})
    return templates.TemplateResponse(
        request,
        "partials/update_banner.html",
        {"version": result["version"], "download_url": result["download_url"]},
    )


@router.post("/download", response_class=HTMLResponse)
def start_download(request: Request) -> HTMLResponse:
    result = update_service.check_update()
    if result["download_url"]:
        update_service.download_update(result["download_url"])
    state = update_service.get_download_state()
    return templates.TemplateResponse(
        request,
        "partials/update_progress.html",
        {"percent": state["percent"], "status": state["status"]},
    )


@router.get("/progress", response_class=HTMLResponse)
def get_progress(request: Request) -> HTMLResponse:
    state = update_service.get_download_state()
    return templates.TemplateResponse(
        request,
        "partials/update_progress.html",
        {"percent": state["percent"], "status": state["status"]},
    )


@router.post("/install", response_class=HTMLResponse)
def do_install(request: Request) -> HTMLResponse:
    result = install_update()
    if result == "not_frozen":
        return templates.TemplateResponse(request, "partials/update_idle.html", {})
    state = {"percent": 100, "status": f"install_error:{result}"}
    return templates.TemplateResponse(
        request,
        "partials/update_progress.html",
        {"percent": 100, "status": state["status"]},
    )
