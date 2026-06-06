# backend/app.py
import sys
import threading
import traceback

import webview
from webview.menu import Menu, MenuAction

from backend import state_store, window_manager
from backend.logger import logger
from backend.main import app as fastapi_app
from backend.server import find_free_port, start_server_thread, wait_for_server
from backend.services.recent_files_service import recent_files_service
from backend.services.window_registry import window_registry


def _patch_app_delegate_for_open_file(callback) -> None:
    """NSApp.finishLaunching() が odoc ハンドラを上書きするため、
    applicationDidFinishLaunching_ で再登録するようにパッチを当てる。"""
    if sys.platform != "darwin":
        return
    try:
        from webview.platforms import cocoa as _cocoa  # type: ignore[import]

        from backend.apple_events import register_open_file_handler

        def _did_finish_launching(self: object, notification: object) -> None:
            logger.info("_did_finish_launching fired: re-registering odoc handler")
            register_open_file_handler(callback)

        _cocoa.BrowserView.AppDelegate.applicationDidFinishLaunching_ = _did_finish_launching
        logger.info("applicationDidFinishLaunching_ patch applied successfully")
    except Exception:
        logger.warning(
            "applicationDidFinishLaunching_ パッチに失敗しました\n%s", traceback.format_exc()
        )


def main() -> None:
    from backend.version import __version__

    logger.info("mmdview %s starting: argv=%s", __version__, sys.argv)

    port = find_free_port()
    start_server_thread(fastapi_app, port)
    wait_for_server(port)

    def _on_open_file(path: str) -> None:
        logger.info("_on_open_file called: path=%s", path)
        recent_files_service.add(path)

        def _run() -> None:
            try:
                window_manager.open_file(path, port)
            except Exception:
                logger.error("open_file failed: path=%s\n%s", path, traceback.format_exc())

        threading.Thread(target=_run, daemon=True).start()

    if len(sys.argv) > 1:
        cli_file = sys.argv[1]
        recent_files_service.add(cli_file)
        window_manager.create_window(port, file_path=cli_file)
    else:
        states = state_store.load_window_states()
        if states:
            for s in states:
                window_manager.create_window(
                    port,
                    file_path=s.get("file"),
                    x=s.get("x", 100),
                    y=s.get("y", 100),
                    width=s.get("width", 1024),
                    height=s.get("height", 768),
                )
        else:
            window_manager.create_window(port)

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
    _patch_app_delegate_for_open_file(_on_open_file)

    def _on_webview_ready() -> None:
        setup_app_menu(port)

    webview.start(menu=menu, func=_on_webview_ready)

    for wid, _ in window_registry.snapshot():
        window_registry.remove(wid)


if __name__ == "__main__":
    main()
