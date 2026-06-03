# backend/update_window.py
"""更新確認ダイアログウィンドウの管理。"""

from __future__ import annotations

import logging
import threading

import webview

from backend.services import update_service

_logger = logging.getLogger(__name__)

HOST = "127.0.0.1"

_update_win: webview.Window | None = None
_menu_target: object | None = None  # NSObject の GC 防止のためモジュールスコープで保持

try:
    import AppKit as _AppKit  # type: ignore[import]

    _NSObject = _AppKit.NSObject

    class _UpdateMenuTarget(_NSObject):  # type: ignore[misc]
        """Check for Updates... メニュー項目のアクションターゲット。"""

        def checkForUpdates_(self, sender: object) -> None:
            # webview.create_window() はメインスレッドから呼ぶと即時描画されないため
            # バックグラウンドスレッドで呼び出す必要がある
            threading.Thread(
                target=open_update_dialog,
                args=(self._port,),  # type: ignore[attr-defined]
                daemon=True,
            ).start()

    class _MenuInstaller(_NSObject):  # type: ignore[misc]
        """メインスレッドでメニュー項目を挿入するヘルパー。"""

        def install_(self, _: object) -> None:
            main_menu = _AppKit.NSApplication.sharedApplication().mainMenu()
            if main_menu is None or main_menu.numberOfItems() == 0:
                return
            app_menu = main_menu.itemAtIndex_(0).submenu()
            if app_menu is None:
                return
            sep = _AppKit.NSMenuItem.separatorItem()
            item = _AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Check for Updates...", "checkForUpdates:", ""
            )
            item.setTarget_(_menu_target)
            app_menu.insertItem_atIndex_(sep, 1)
            app_menu.insertItem_atIndex_(item, 2)

    _APPKIT_AVAILABLE = True

except ImportError:
    _APPKIT_AVAILABLE = False


def open_update_dialog(port: int) -> None:
    """更新確認ダイアログを開く。すでに開いていれば何もしない。"""
    global _update_win
    if _update_win is not None:
        return
    update_service.invalidate_cache()
    url = f"http://{HOST}:{port}/api/update/dialog"
    win = webview.create_window(
        title="アップデート確認",
        url=url,
        width=400,
        height=260,
        resizable=False,
    )
    if win is None:
        return

    def _on_closed() -> None:
        global _update_win
        _update_win = None

    win.events.closed += _on_closed
    _update_win = win


def setup_app_menu(port: int) -> None:
    """macOS アプリケーションメニューに「Check for Updates...」を追加する。

    webview.start(func=...) のコールバックから呼び出す。
    """
    global _menu_target
    try:
        _menu_target = _UpdateMenuTarget.alloc().init()
        _menu_target._port = port  # type: ignore[attr-defined]
        installer = _MenuInstaller.alloc().init()
        installer.performSelectorOnMainThread_withObject_waitUntilDone_("install:", None, True)
    except Exception as e:
        _logger.warning("メニュー設定に失敗しました: %s", e)
