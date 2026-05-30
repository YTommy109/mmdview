from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from backend.paths import TEMPLATES_DIR
from backend.services.watch_service import watch_service

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _pick_file() -> str | None:
    import webview
    result = webview.windows[0].create_file_dialog(
        webview.OPEN_DIALOG,
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.md)", "All files (*.*)"),
    )
    return result[0] if result else None


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    content = watch_service.get_content()
    path = watch_service.get_path()
    if content is None:
        return templates.TemplateResponse(request, "welcome.html")
    return templates.TemplateResponse(request, "viewer.html", {
        "content": content,
        "filename": path.name,
        "filepath": str(path),
    })


@router.post("/open-file")
async def open_file() -> Response:
    path = _pick_file()
    if path:
        watch_service.set_file(path)
    return Response(headers={"HX-Redirect": "/"})
