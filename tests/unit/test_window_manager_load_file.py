from unittest.mock import MagicMock, patch

import backend.window_manager as wm


def test_load_file_into_window_sets_watch_title_and_reloads():
    window = MagicMock()
    watch = MagicMock()
    wm._windows["target-id"] = window
    try:
        with patch.object(wm.window_registry, "get_watch", return_value=watch):
            result = wm.load_file_into_window("target-id", "/tmp/dia.mmd")
    finally:
        wm._windows.pop("target-id", None)

    assert result is True
    watch.set_file.assert_called_once_with("/tmp/dia.mmd")
    window.set_title.assert_called_once_with("dia.mmd")
    window.evaluate_js.assert_called_once_with("location.reload()")


def test_load_file_into_window_returns_false_for_unknown_id():
    assert wm.load_file_into_window("no-such-id", "/tmp/dia.mmd") is False
