# tests/unit/test_state_store.py
import json
from unittest.mock import patch

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
