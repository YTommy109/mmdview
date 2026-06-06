from pathlib import Path
from unittest.mock import MagicMock, patch


def test_load_window_states_returns_empty_on_oserror():
    """WINDOW_STATE_FILE が存在するが read_text() が OSError を投げる場合、
    空リストを返すことを確認する。"""
    import backend.app as app_module

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = True
    fake_path.read_text.side_effect = OSError("Permission denied")

    with patch.object(app_module, "WINDOW_STATE_FILE", fake_path):
        result = app_module._load_window_states()

    assert result == []


def test_load_window_states_returns_empty_when_file_absent():
    """WINDOW_STATE_FILE が存在しない場合、空リストを返すことを確認する。"""
    import backend.app as app_module

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = False

    with patch.object(app_module, "WINDOW_STATE_FILE", fake_path):
        result = app_module._load_window_states()

    assert result == []


def test_load_window_states_backward_compat_with_dict():
    """旧形式（辞書）の JSON が保存されている場合、リストに変換して返すことを確認する。"""
    import json

    import backend.app as app_module

    old_state = {"x": 200, "y": 150, "width": 1280, "height": 800, "last_file": "/a/foo.mmd"}

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = True
    fake_path.read_text.return_value = json.dumps(old_state)

    with patch.object(app_module, "WINDOW_STATE_FILE", fake_path):
        result = app_module._load_window_states()

    assert len(result) == 1
    assert result[0]["x"] == 200
    assert result[0]["file"] == "/a/foo.mmd"


def test_load_window_states_returns_list_format(tmp_path):
    """リスト形式の JSON が保存されている場合、正しく読み込まれることを確認する。"""
    import json

    import backend.app as app_module

    state_file = tmp_path / "window_state.json"
    states = [
        {"x": 100, "y": 200, "width": 800, "height": 600, "file": "/a/b.mmd"},
        {"x": 300, "y": 400, "width": 1024, "height": 768, "file": "/c/d.mmd"},
    ]
    state_file.write_text(json.dumps(states), encoding="utf-8")

    with patch.object(app_module, "WINDOW_STATE_FILE", state_file):
        result = app_module._load_window_states()

    assert len(result) == 2
    assert result[0]["file"] == "/a/b.mmd"
    assert result[1]["file"] == "/c/d.mmd"
