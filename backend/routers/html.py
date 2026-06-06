from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.paths import TEMPLATES_DIR
from backend.services.window_registry import window_registry

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, window_id: str = "") -> HTMLResponse:
    watch = window_registry.get_watch(window_id)
    if watch is None:
        return templates.TemplateResponse(request, "welcome.html")
    content = watch.get_content()
    path = watch.get_path()
    if content is None or path is None:
        return templates.TemplateResponse(request, "welcome.html")
    return templates.TemplateResponse(
        request,
        "viewer.html",
        {"content": content},
    )
