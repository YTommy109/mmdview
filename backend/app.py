import json
import socket
import threading
import time

import uvicorn
import webview
from webview import FileDialog
from webview.menu import Menu, MenuAction, MenuSeparator

from backend.main import app
from backend.paths import WINDOW_STATE_FILE
from backend.services.watch_service import watch_service

_DEFAULT_STATE: dict = {"x": 100, "y": 100, "width": 1024, "height": 768, "last_file": None}


def _load_window_state() -> dict:
    if WINDOW_STATE_FILE.exists():
        try:
            return json.loads(WINDOW_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            pass
    return _DEFAULT_STATE.copy()


def _save_window_state(window: webview.Window) -> None:
    state = {
        "x": window.x,
        "y": window.y,
        "width": window.width,
        "height": window.height,
        "last_file": str(watch_service.get_path()) if watch_service.get_path() else None,
    }
    WINDOW_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int) -> None:
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


def _wait_for_server(port: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"Server did not start on port {port} within {timeout}s")


def _open_file_from_menu(window: webview.Window) -> None:
    result = window.create_file_dialog(
        FileDialog.OPEN,
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.md)", "All files (*.*)"),
    )
    if result:
        watch_service.set_file(result[0])
        window.evaluate_js("window.location.reload()")


def main() -> None:
    port = _find_free_port()
    state = _load_window_state()

    if state.get("last_file"):
        watch_service.set_file(state["last_file"])

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()
    _wait_for_server(port)

    window = webview.create_window(
        "mmdview",
        f"http://127.0.0.1:{port}/",
        x=state.get("x", 100),
        y=state.get("y", 100),
        width=state.get("width", 1024),
        height=state.get("height", 768),
    )
    assert window is not None

    _save_timer: threading.Timer | None = None

    def _schedule_save() -> None:
        nonlocal _save_timer
        if _save_timer:
            _save_timer.cancel()
        _save_timer = threading.Timer(0.5, _save_window_state, args=(window,))
        _save_timer.start()

    window.events.moved += lambda x, y: _schedule_save()
    window.events.resized += lambda width, height: _schedule_save()

    menu = [
        Menu(
            "File",
            [
                MenuAction("Open...", lambda: _open_file_from_menu(window)),
                MenuSeparator(),
                MenuAction("Close", window.destroy),
            ],
        )
    ]

    from backend.update_window import setup_app_menu

    webview.start(menu=menu, func=lambda: setup_app_menu(port))
    watch_service.stop()


if __name__ == "__main__":
    main()
