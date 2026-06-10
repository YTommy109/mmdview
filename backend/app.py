# backend/app.py
import sys
import threading
import traceback
from pathlib import Path

import webview
from webview.menu import Menu, MenuAction

from backend import state_store, window_manager
from backend.logger import logger
from backend.main import app as fastapi_app
from backend.server import find_free_port, start_server_thread, wait_for_server
from backend.services.recent_files_service import recent_files_service
from backend.services.window_registry import window_registry


def _patch_app_delegate_for_open_file(callback, launch_finished: threading.Event) -> None:
    """NSApp.finishLaunching() が odoc ハンドラを上書きするため、
    applicationDidFinishLaunching_ で再登録するようにパッチを当てる。
    また application:openFile: を実装して起動時のエラーダイアログを抑止する。
    パッチ失敗時は launch_finished を即セットし、起動処理が待ち続けないようにする。"""
    if sys.platform != "darwin":
        launch_finished.set()
        return
    try:
        from webview.platforms import cocoa as _cocoa  # type: ignore[import]

        from backend.apple_events import register_open_file_handler

        def _did_finish_launching(self: object, notification: object) -> None:
            logger.info("_did_finish_launching fired: re-registering odoc handler")
            register_open_file_handler(callback)
            launch_finished.set()

        def _application_open_file(self: object, app: object, filename: str) -> bool:
            # macOS が kAEOpenDocuments を application:openFile: 経由で届ける場合に呼ばれる。
            # YES を返してエラーダイアログを抑止し、コールバックでファイルを開く。
            logger.info("application_openFile_ called: %s", filename)
            callback(str(filename))
            return True

        def _application_will_terminate(self: object, notification: object) -> None:
            logger.info("applicationWillTerminate_ fired: saving all window states")
            window_manager.save_all_for_terminate()

        _cocoa.BrowserView.AppDelegate.applicationDidFinishLaunching_ = _did_finish_launching
        _cocoa.BrowserView.AppDelegate.application_openFile_ = _application_open_file
        _cocoa.BrowserView.AppDelegate.applicationWillTerminate_ = _application_will_terminate
        logger.info("AppDelegate patches applied successfully")
    except Exception:
        logger.warning("AppDelegate パッチに失敗しました\n%s", traceback.format_exc())
        launch_finished.set()


class _StartupFileGate:
    """起動中に Apple Event で届いたファイルパスを溜めるゲート。

    run loop が安定する前にバックグラウンドスレッドから webview.create_window を
    呼ぶと、最初のウィンドウ扱い（uid='master'）になった場合に NSWindow が
    メインスレッド外で生成されてクラッシュするため、起動が解決するまで
    ファイルオープンをキューに溜める。"""

    def __init__(self) -> None:
        self.launch_finished = threading.Event()
        self.file_arrived = threading.Event()
        self._lock = threading.Lock()
        self._pending: list[str] = []
        self._resolved = False

    def queue(self, path: str) -> bool:
        """起動解決前ならパスを溜めて True を返す。解決後は False。"""
        with self._lock:
            if self._resolved:
                return False
            self._pending.append(path)
        self.file_arrived.set()
        return True

    def drain(self) -> list[str]:
        """ゲートを閉じ、溜まったパスを返す。以後 queue は False を返す。"""
        with self._lock:
            self._resolved = True
            pending = self._pending
            self._pending = []
            return pending


def _resolve_startup_window(
    gate: _StartupFileGate,
    blank_window_id: str | None,
    port: int,
    timeout: float = 5.0,
    grace: float = 0.5,
) -> None:
    """起動時の空ウィンドウとキュー済みファイルの扱いを決める。

    "このアプリで開く" によるコールド起動ではファイルが argv ではなく
    Apple Event（application:openFile:）で届くため、didFinishLaunching まで
    待ってから判断する。ファイルが届いていればオープンダイアログを出さずに
    空ウィンドウへ読み込み、届いていなければ従来どおりダイアログを表示する。"""
    gate.launch_finished.wait(timeout=timeout)
    if blank_window_id is not None:
        gate.file_arrived.wait(timeout=grace)
    paths = gate.drain()
    if blank_window_id is None:
        for path in paths:
            window_manager.open_file(path, port)
        return
    if not paths:
        window_manager.open_file_for_window(blank_window_id, port)
        return
    logger.info("startup: %d file(s) arrived via event, skipping open dialog", len(paths))
    if not window_manager.load_file_into_window(blank_window_id, paths[0]):
        window_manager.open_file(paths[0], port)
    for path in paths[1:]:
        window_manager.open_file(path, port)


def main() -> None:
    from backend.version import __version__

    logger.info("mmdview %s starting: argv=%s", __version__, sys.argv)

    port = find_free_port()
    start_server_thread(fastapi_app, port)
    wait_for_server(port)

    gate = _StartupFileGate()

    def _on_open_file(path: str) -> None:
        logger.info("_on_open_file called: path=%s", path)
        recent_files_service.add(path)
        if gate.queue(path):
            logger.info("startup gate: queued %s", path)
            return

        def _run() -> None:
            try:
                window_manager.open_file(path, port)
            except Exception:
                logger.error("open_file failed: path=%s\n%s", path, traceback.format_exc())

        threading.Thread(target=_run, daemon=True).start()

    startup_blank_id: str | None = None

    if len(sys.argv) > 1:
        cli_file = sys.argv[1]
        recent_files_service.add(cli_file)
        window_manager.create_window(port, file_path=cli_file)
    else:
        states = state_store.load_window_states()
        restorable = [s for s in states if s.get("file") and Path(s["file"]).exists()]
        if restorable:
            for s in restorable:
                window_manager.create_window(
                    port,
                    file_path=s.get("file"),
                    x=s.get("x") or 100,
                    y=s.get("y") or 100,
                    width=s.get("width") or 1024,
                    height=s.get("height") or 768,
                )
        else:
            wid, _ = window_manager.create_window(port)
            startup_blank_id = wid

    menu = [
        Menu(
            "File",
            [
                MenuAction("Open...", lambda: window_manager.open_file_from_menu(port)),
                window_manager.build_open_recent_menu(port),
            ],
        )
    ]

    from backend.apple_events import register_open_file_handler
    from backend.update_window import setup_app_menu

    register_open_file_handler(_on_open_file)
    _patch_app_delegate_for_open_file(_on_open_file, gate.launch_finished)

    def _on_webview_ready() -> None:
        setup_app_menu(port)
        _resolve_startup_window(gate, startup_blank_id, port)

    webview.start(menu=menu, func=_on_webview_ready)

    for wid, _ in window_registry.snapshot():
        window_registry.remove(wid)


if __name__ == "__main__":
    main()
