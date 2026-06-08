from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("AppKit")

# backend.apple_events をここで先にインポートし sys.modules に載せる。
# patch.dict が with ブロック終了時に sys.modules を元に戻す際、
# ブロック開始前に存在したモジュールは削除されないため、
# 二度目の _patch_app_delegate_for_open_file 呼び出しで ObjC クラス再定義エラーが
# 起きるのを防ぐ。
import backend.apple_events  # noqa: F401, E402
from backend.app import _patch_app_delegate_for_open_file  # noqa: E402


def _apply_patch(callback):
    """モックした AppDelegate クラスにパッチを当て、クラスを返す。"""
    mock_cocoa = MagicMock()
    mock_delegate_class = MagicMock()
    mock_cocoa.BrowserView.AppDelegate = mock_delegate_class

    with (
        patch.dict("sys.modules", {"webview.platforms.cocoa": mock_cocoa}),
        patch("backend.apple_events.register_open_file_handler"),
    ):
        _patch_app_delegate_for_open_file(callback)

    return mock_delegate_class


def test_application_open_file_calls_callback_and_returns_true():
    received: list[str] = []
    delegate = _apply_patch(received.append)

    fn = delegate.application_openFile_
    result = fn(None, None, "/path/to/test.mmd")

    assert result is True
    assert received == ["/path/to/test.mmd"]


def test_application_open_file_converts_filename_to_str():
    received: list[str] = []
    delegate = _apply_patch(received.append)

    fn = delegate.application_openFile_
    mock_nsstring = MagicMock()
    mock_nsstring.__str__ = lambda self: "/nsstring/path.mmd"
    fn(None, None, mock_nsstring)

    assert received[0] == str(mock_nsstring)


def test_application_will_terminate_calls_save_all_for_terminate():
    """applicationWillTerminate_ が save_all_for_terminate を呼ぶことを確認する。"""
    import backend.window_manager as wm

    delegate = _apply_patch(lambda p: None)

    with patch.object(wm, "save_all_for_terminate") as mock_save:
        fn = delegate.applicationWillTerminate_
        fn(None, None)

    mock_save.assert_called_once()
