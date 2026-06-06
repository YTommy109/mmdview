# tests/unit/test_state_store.py
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.state_store import load_window_states


def _patch_state_file(tmp_path, content):
    state_file = tmp_path / "window_state.json"
    if content is not None:
        state_file.write_text(json.dumps(content), encoding="utf-8")
    return state_file


def test_load_window_states_ファイルなしで空リストを返す(tmp_path):
    state_file = tmp_path / "window_state.json"
    with patch("backend.state_store.WINDOW_STATE_FILE", state_file):
        result = load_window_states()
    assert result == []


def test_load_window_states_リスト形式を読み込む(tmp_path):
    data = [{"x": 10, "y": 20, "width": 800, "height": 600, "file": "/tmp/a.mmd"}]
    state_file = _patch_state_file(tmp_path, data)
    with patch("backend.state_store.WINDOW_STATE_FILE", state_file):
        result = load_window_states()
    assert result == data


def test_load_window_states_旧形式dictを変換する(tmp_path):
    data = {"x": 50, "y": 60, "width": 1024, "height": 768, "last_file": "/tmp/b.mmd"}
    state_file = _patch_state_file(tmp_path, data)
    with patch("backend.state_store.WINDOW_STATE_FILE", state_file):
        result = load_window_states()
    assert len(result) == 1
    assert result[0]["x"] == 50
    assert result[0]["file"] == "/tmp/b.mmd"


def test_load_window_states_壊れたJSONで空リストを返す(tmp_path):
    state_file = tmp_path / "window_state.json"
    state_file.write_text("INVALID JSON", encoding="utf-8")
    with patch("backend.state_store.WINDOW_STATE_FILE", state_file):
        result = load_window_states()
    assert result == []


def test_save_all_states_正常にJSONを書き込む(tmp_path):
    from backend.state_store import save_all_states

    state_file = tmp_path / "window_state.json"

    mock_win = MagicMock()
    mock_win.x = 10
    mock_win.y = 20
    mock_win.width = 800
    mock_win.height = 600

    mock_watch = MagicMock()
    mock_watch.get_path.return_value = Path("/tmp/test.mmd")

    windows = {"w1": mock_win}

    with (
        patch("backend.state_store.WINDOW_STATE_FILE", state_file),
        patch("backend.state_store.window_registry.get_watch", return_value=mock_watch),
    ):
        save_all_states(windows)

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["x"] == 10
    assert data[0]["file"] == "/tmp/test.mmd"


def test_save_all_states_空ウィンドウで空リストを書き込む(tmp_path):
    from backend.state_store import save_all_states

    state_file = tmp_path / "window_state.json"

    with patch("backend.state_store.WINDOW_STATE_FILE", state_file):
        save_all_states({})

    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data == []
