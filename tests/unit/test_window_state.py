from pathlib import Path
from unittest.mock import MagicMock, patch


def test_load_window_states_returns_empty_on_oserror():
    """WINDOW_STATE_FILE が存在するが read_text() が OSError を投げる場合、
    空リストを返すことを確認する。"""
    import backend.state_store as state_store_module

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = True
    fake_path.read_text.side_effect = OSError("Permission denied")

    with patch.object(state_store_module, "WINDOW_STATE_FILE", fake_path):
        result = state_store_module.load_window_states()

    assert result == []
