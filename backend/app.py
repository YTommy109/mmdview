# backend/app.py
import json
import socket
import sys
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import uvicorn
import webview
from webview import FileDialog
from webview.menu import Menu, MenuAction, MenuSeparator

from backend.logger import logger
from backend.main import app
from backend.paths import WINDOW_STATE_FILE
from backend.services.recent_files_service import recent_files_service
from backend.services.window_registry import window_registry

# window_id → webview.Window の対応表
_windows: dict[str, webview.Window] = {}


def _load_window_states() -> list[dict]:
    """保存済みウィンドウ状態をリストで返す。ファイルがなければ空リスト。"""
    if WINDOW_STATE_FILE.exists():
        try:
            data = json.loads(WINDOW_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # 旧形式（シングルウィンドウ）に後方互換
                return [
                    {
                        "x": data.get("x", 100),
                        "y": data.get("y", 100),
                        "width": data.get("width", 1024),
                        "height": data.get("height", 768),
                        "file": data.get("last_file"),
                    }
                ]
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return []


def _save_all_states() -> None:
    """全ウィンドウの状態を JSON リストとして保存する。"""
    states = []
    for wid, win in list(_windows.items()):
        watch = window_registry.get_watch(wid)
        path = watch.get_path() if watch else None
        states.append(
            {
                "x": win.x,
                "y": win.y,
                "width": win.width,
                "height": win.height,
                "file": str(path) if path else None,
            }
        )
    try:
        WINDOW_STATE_FILE.write_text(json.dumps(states), encoding="utf-8")
    except OSError:
        logger.error("_save_all_states: 書き込み失敗\n%s", traceback.format_exc())


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


def _focus_window(window: webview.Window) -> None:
    """ウィンドウをフロントに持ってくるベストエフォート実装。"""
    try:
        window.evaluate_js("window.focus()")
        if sys.platform == "darwin":
            from AppKit import NSApp  # type: ignore[import]

            NSApp.activateIgnoringOtherApps_(True)
    except Exception:
        pass


def _create_window(
    port: int,
    file_path: str | None = None,
    x: int = 100,
    y: int = 100,
    width: int = 1024,
    height: int = 768,
) -> tuple[str, webview.Window]:
    """新しいウィンドウを作成し、registry と _windows に登録して返す。"""
    window_id = str(uuid4())
    window_registry.create(window_id, file_path)

    title = Path(file_path).name if file_path else "mmdview"
    try:
        window = webview.create_window(
            title,
            f"http://127.0.0.1:{port}/?window_id={window_id}",
            x=x,
            y=y,
            width=width,
            height=height,
        )
    except Exception:
        window_registry.remove(window_id)
        raise

    if window is None:
        window_registry.remove(window_id)
        raise RuntimeError(f"webview.create_window returned None for window_id={window_id}")

    _windows[window_id] = window

    # 各ウィンドウが自分用の debounce タイマーを持つ
    _save_timer: threading.Timer | None = None

    def _schedule_save() -> None:
        nonlocal _save_timer
        if _save_timer:
            _save_timer.cancel()
        _save_timer = threading.Timer(0.5, _save_all_states)
        _save_timer.start()

    window.events.moved += lambda x, y: _schedule_save()
    window.events.resized += lambda width, height: _schedule_save()

    def _on_closed() -> None:
        _windows.pop(window_id, None)
        window_registry.remove(window_id)
        _save_all_states()

    window.events.closed += _on_closed
    return window_id, window


def _open_file(path: str, port: int) -> None:
    """ファイルを開く。既に開いていれば既存ウィンドウをフォーカスし、なければ新規作成。"""
    existing_id = window_registry.find_by_path(path)
    if existing_id:
        win = _windows.get(existing_id)
        if win is not None:
            logger.info("_open_file: already open, focusing: %s", path)
            _focus_window(win)
            return
    logger.info("_open_file: opening new window: %s", path)
    _create_window(port, file_path=path)


def _open_file_from_menu(port: int) -> None:
    if not webview.windows:
        return
    result = webview.windows[0].create_file_dialog(
        FileDialog.OPEN,
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    if result:
        recent_files_service.add(result[0])
        _open_file(result[0], port)


def _build_open_recent_menu(port: int) -> Menu:
    recent = recent_files_service.get()

    def _open_recent(path: str) -> None:
        recent_files_service.add(path)
        _open_file(path, port)

    if recent:
        items: list = [MenuAction(p, lambda p=p: _open_recent(p)) for p in recent]
        items += [MenuSeparator(), MenuAction("Clear Menu", recent_files_service.clear)]
    else:
        items = [MenuAction("No Recent Files", lambda: None)]

    return Menu("Open Recent...", items)


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

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()
    _wait_for_server(port)

    def _on_open_file(path: str) -> None:
        logger.info("_on_open_file called: path=%s", path)
        try:
            recent_files_service.add(path)
            _open_file(path, port)
        except Exception:
            logger.error("_on_open_file failed: path=%s\n%s", path, traceback.format_exc())

    # 初期ウィンドウの決定
    if len(sys.argv) > 1:
        cli_file = sys.argv[1]
        recent_files_service.add(cli_file)
        _create_window(port, file_path=cli_file)
    else:
        states = _load_window_states()
        if states:
            for s in states:
                _create_window(
                    port,
                    file_path=s.get("file"),
                    x=s.get("x", 100),
                    y=s.get("y", 100),
                    width=s.get("width", 1024),
                    height=s.get("height", 768),
                )
        else:
            _create_window(port)

    menu = [
        Menu(
            "File",
            [
                MenuAction("Open...", lambda: _open_file_from_menu(port)),
                _build_open_recent_menu(port),
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

    # アプリ終了時に全ウィンドウをクリーンアップ
    for wid, _ in window_registry.snapshot():
        window_registry.remove(wid)


if __name__ == "__main__":
    main()
