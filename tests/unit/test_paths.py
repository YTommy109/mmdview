def test_app_data_dir_exists():
    from backend.paths import APP_DATA_DIR

    assert APP_DATA_DIR.exists()
    assert APP_DATA_DIR.is_dir()


def test_window_state_file_path():
    from backend.paths import APP_DATA_DIR, WINDOW_STATE_FILE

    assert WINDOW_STATE_FILE.parent == APP_DATA_DIR
    assert WINDOW_STATE_FILE.name == "window_state.json"
