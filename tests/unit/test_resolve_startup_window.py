import threading
from unittest.mock import patch

from backend.app import _resolve_startup_window, _StartupFileGate


def _gate(launch_finished: bool = True, paths: tuple[str, ...] = ()) -> _StartupFileGate:
    gate = _StartupFileGate()
    if launch_finished:
        gate.launch_finished.set()
    for path in paths:
        gate.queue(path)
    return gate


def _patches():
    return (
        patch("backend.window_manager.load_file_into_window", return_value=True),
        patch("backend.window_manager.open_file_for_window"),
        patch("backend.window_manager.open_file"),
    )


def test_gate_queues_until_drained():
    gate = _StartupFileGate()

    assert gate.queue("/a.mmd") is True
    assert gate.drain() == ["/a.mmd"]
    assert gate.queue("/b.mmd") is False
    assert gate.drain() == []


def test_resolve_loads_queued_file_into_blank_window():
    """Apple Event でファイルが届いた場合、ダイアログを出さず空ウィンドウに読み込む。"""
    gate = _gate(paths=("/a.mmd",))
    p_load, p_dialog, p_open = _patches()

    with p_load as mock_load, p_dialog as mock_dialog, p_open as mock_open:
        _resolve_startup_window(gate, "blank-id", 8000)

    mock_load.assert_called_once_with("blank-id", "/a.mmd")
    mock_dialog.assert_not_called()
    mock_open.assert_not_called()


def test_resolve_opens_second_and_later_files_in_new_windows():
    gate = _gate(paths=("/a.mmd", "/b.mmd"))
    p_load, p_dialog, p_open = _patches()

    with p_load as mock_load, p_dialog, p_open as mock_open:
        _resolve_startup_window(gate, "blank-id", 8000)

    mock_load.assert_called_once_with("blank-id", "/a.mmd")
    mock_open.assert_called_once_with("/b.mmd", 8000)


def test_resolve_opens_dialog_when_no_file_event():
    gate = _gate()
    p_load, p_dialog, p_open = _patches()

    with p_load as mock_load, p_dialog as mock_dialog, p_open:
        _resolve_startup_window(gate, "blank-id", 8000, grace=0.01)

    mock_dialog.assert_called_once_with("blank-id", 8000)
    mock_load.assert_not_called()


def test_resolve_opens_queued_files_when_no_blank_window():
    """復元起動などで空ウィンドウがない場合もキュー済みファイルを開く。"""
    gate = _gate(paths=("/a.mmd",))
    p_load, p_dialog, p_open = _patches()

    with p_load as mock_load, p_dialog as mock_dialog, p_open as mock_open:
        _resolve_startup_window(gate, None, 8000)

    mock_open.assert_called_once_with("/a.mmd", 8000)
    mock_load.assert_not_called()
    mock_dialog.assert_not_called()


def test_resolve_falls_back_to_new_window_when_blank_already_gone():
    gate = _gate(paths=("/a.mmd",))
    p_load, p_dialog, p_open = _patches()

    with p_load as mock_load, p_dialog, p_open as mock_open:
        mock_load.return_value = False
        _resolve_startup_window(gate, "blank-id", 8000)

    mock_open.assert_called_once_with("/a.mmd", 8000)


def test_resolve_waits_for_launch_finished_before_deciding():
    """didFinishLaunching 前に判断しない。直前に届いたファイルイベントも考慮される。"""
    gate = _gate(launch_finished=False)

    def _fire() -> None:
        gate.queue("/late.mmd")
        gate.launch_finished.set()

    timer = threading.Timer(0.05, _fire)
    timer.start()
    p_load, p_dialog, p_open = _patches()
    try:
        with p_load as mock_load, p_dialog as mock_dialog, p_open:
            _resolve_startup_window(gate, "blank-id", 8000, timeout=1.0)
    finally:
        timer.cancel()

    mock_load.assert_called_once_with("blank-id", "/late.mmd")
    mock_dialog.assert_not_called()
