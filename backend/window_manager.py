# backend/window_manager.py
import sys
import threading
from pathlib import Path
from uuid import uuid4

import webview
from webview import FileDialog
from webview.menu import Menu, MenuAction, MenuSeparator

from backend import state_store
from backend.logger import logger
from backend.services.recent_files_service import recent_files_service
from backend.services.window_registry import window_registry

_windows: dict[str, webview.Window] = {}


def get_windows() -> dict[str, webview.Window]:
    return dict(_windows)


def focus_window(window: webview.Window) -> None:
    """ウィンドウをフロントに持ってくるベストエフォート実装。"""
    try:
        window.evaluate_js("window.focus()")
        if sys.platform == "darwin":
            from AppKit import NSApp  # type: ignore[import]

            NSApp.activateIgnoringOtherApps_(True)
    except Exception:
        pass


def create_window(
    port: int,
    file_path: str | None = None,
    x: int = 100,
    y: int = 100,
    width: int = 1024,
    height: int = 768,
) -> tuple[str, webview.Window]:
    """新しいウィンドウを作成し、registry と _windows に登録して返す。"""
    window_id = str(uuid4())
    logger.info("create_window: file_path=%s window_id=%s", file_path, window_id)
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

    _save_timer: threading.Timer | None = None

    def _schedule_save() -> None:
        nonlocal _save_timer
        if _save_timer:
            _save_timer.cancel()
        _save_timer = threading.Timer(0.5, lambda: state_store.save_all_states(_windows))
        _save_timer.start()

    window.events.moved += lambda x, y: _schedule_save()
    window.events.resized += lambda width, height: _schedule_save()

    def _on_closed() -> None:
        _windows.pop(window_id, None)
        window_registry.remove(window_id)
        state_store.save_all_states(_windows)

    window.events.closed += _on_closed
    return window_id, window


def open_file(path: str, port: int) -> None:
    """ファイルを開く。既に開いていれば既存ウィンドウをフォーカスし、なければ新規作成。"""
    existing_id = window_registry.find_by_path(path)
    if existing_id:
        win = _windows.get(existing_id)
        if win is not None:
            logger.info("open_file: already open, focusing: %s", path)
            focus_window(win)
            return
        logger.warning(
            "open_file: registry has window_id=%s but not in _windows, opening new: %s",
            existing_id,
            path,
        )
    logger.info("open_file: opening new window: %s", path)
    create_window(port, file_path=path)


def _get_initial_directory() -> str:
    recent = recent_files_service.get()
    if recent:
        parent = Path(recent[0]).parent
        if parent.is_dir():
            return str(parent)
    return str(Path.home() / "Documents")


def open_file_from_menu(port: int) -> None:
    if not webview.windows:
        return
    result = webview.windows[0].create_file_dialog(
        FileDialog.OPEN,
        directory=_get_initial_directory(),
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    if result:
        recent_files_service.add(result[0])
        open_file(result[0], port)


def open_file_for_window(window_id: str, port: int) -> None:
    """起動時の空ウィンドウにファイルを読み込む。
    ファイル選択時は既存ウィンドウを再利用し、キャンセル時はウィンドウを閉じる。"""
    win = _windows.get(window_id)
    if win is None:
        return
    result = win.create_file_dialog(
        FileDialog.OPEN,
        directory=_get_initial_directory(),
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    if result:
        path = result[0]
        recent_files_service.add(path)
        watch = window_registry.get_watch(window_id)
        if watch:
            watch.set_file(path)
        win.set_title(Path(path).name)
        win.evaluate_js("location.reload()")
    else:
        win.destroy()


def build_open_recent_menu(port: int) -> Menu:
    recent = recent_files_service.get()

    def _open_recent(path: str) -> None:
        recent_files_service.add(path)
        open_file(path, port)

    if recent:
        items: list = [MenuAction(p, lambda p=p: _open_recent(p)) for p in recent]
        items += [MenuSeparator(), MenuAction("Clear Menu", recent_files_service.clear)]
    else:
        items = [MenuAction("No Recent Files", lambda: None)]

    return Menu("Open Recent...", items)
