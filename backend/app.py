import json
import socket
import sys
import threading
import time
from collections.abc import Callable

import uvicorn
import webview
from webview import FileDialog
from webview.menu import Menu, MenuAction, MenuSeparator

from backend.logger import logger
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
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    if result:
        watch_service.set_file(result[0])
        window.evaluate_js("window.location.reload()")


def _patch_app_delegate_for_open_file(callback: Callable[[str], None]) -> None:
    """NSApp.finishLaunching() が odoc ハンドラを上書きするため、
    applicationDidFinishLaunching_ で再登録するようにパッチを当てる。"""
    if sys.platform != "darwin":
        return
    try:
        from webview.platforms import cocoa as _cocoa  # type: ignore[import]

        from backend.apple_events import register_open_file_handler

        def _did_finish_launching(self: object, notification: object) -> None:
            register_open_file_handler(callback)

        _cocoa.BrowserView.AppDelegate.applicationDidFinishLaunching_ = _did_finish_launching
    except Exception:
        logger.warning("applicationDidFinishLaunching_ パッチに失敗しました")


def main() -> None:
    from backend.version import __version__

    logger.info("mmdview %s starting: argv=%s", __version__, sys.argv)

    port = _find_free_port()
    state = _load_window_state()

    initial_file = (sys.argv[1] if len(sys.argv) > 1 else None) or state.get("last_file")
    if initial_file:
        watch_service.set_file(initial_file)

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()
    _wait_for_server(port)

    def _on_open_file(path: str) -> None:
        logger.info("_on_open_file called: path=%s", path)
        try:
            watch_service.set_file(path)
        except Exception:
            import traceback

            logger.error("watch_service.set_file failed: path=%s\n%s", path, traceback.format_exc())
            return

        def _reload() -> None:
            try:
                for win in webview.windows:
                    win.evaluate_js("window.location.reload()")
            except Exception:
                import traceback

                logger.error("_reload failed:\n%s", traceback.format_exc())

        threading.Thread(target=_reload, daemon=True).start()

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

    from backend.apple_events import register_open_file_handler
    from backend.update_window import setup_app_menu

    register_open_file_handler(_on_open_file)
    _patch_app_delegate_for_open_file(_on_open_file)

    def _on_webview_ready() -> None:
        setup_app_menu(port)

    webview.start(menu=menu, func=_on_webview_ready)
    watch_service.stop()


if __name__ == "__main__":
    main()
