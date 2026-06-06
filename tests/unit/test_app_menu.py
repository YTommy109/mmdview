from unittest.mock import MagicMock, patch

from webview.menu import Menu, MenuAction, MenuSeparator

from backend.window_manager import build_open_recent_menu, open_file_from_menu


def _action_titles(menu: Menu) -> list[str]:
    return [item.title for item in menu.items if isinstance(item, MenuAction)]


def _has_separator(menu: Menu) -> bool:
    return any(isinstance(item, MenuSeparator) for item in menu.items)


# ---------------------------------------------------------------------------
# build_open_recent_menu
# ---------------------------------------------------------------------------


@patch("backend.window_manager.recent_files_service")
def test_menu_title_is_open_recent(mock_svc):
    mock_svc.get.return_value = []
    menu = build_open_recent_menu(8080)
    assert menu.title == "Open Recent..."


@patch("backend.window_manager.recent_files_service")
def test_no_recent_files_shows_placeholder(mock_svc):
    mock_svc.get.return_value = []
    menu = build_open_recent_menu(8080)
    assert _action_titles(menu) == ["No Recent Files"]
    assert not _has_separator(menu)


@patch("backend.window_manager.recent_files_service")
def test_recent_files_appear_as_menu_items(mock_svc):
    mock_svc.get.return_value = ["/a/foo.mmd", "/b/bar.mmd"]
    menu = build_open_recent_menu(8080)
    titles = _action_titles(menu)
    assert "/a/foo.mmd" in titles
    assert "/b/bar.mmd" in titles


@patch("backend.window_manager.recent_files_service")
def test_recent_files_menu_has_separator_and_clear(mock_svc):
    mock_svc.get.return_value = ["/a/foo.mmd"]
    menu = build_open_recent_menu(8080)
    assert _has_separator(menu)
    assert "Clear Menu" in _action_titles(menu)


@patch("backend.window_manager.open_file")
@patch("backend.window_manager.recent_files_service")
def test_clicking_recent_file_opens_it(mock_recent_svc, mock_open_file):
    path = "/a/foo.mmd"
    mock_recent_svc.get.return_value = [path]
    port = 8080

    menu = build_open_recent_menu(port)

    file_action = next(
        item for item in menu.items if isinstance(item, MenuAction) and item.title == path
    )
    file_action.function()

    mock_recent_svc.add.assert_called_once_with(path)
    mock_open_file.assert_called_once_with(path, port)


@patch("backend.window_manager.recent_files_service")
def test_clear_menu_action_calls_clear(mock_svc):
    mock_svc.get.return_value = ["/a/foo.mmd"]
    menu = build_open_recent_menu(8080)

    clear_action = next(
        item for item in menu.items if isinstance(item, MenuAction) and item.title == "Clear Menu"
    )
    clear_action.function()

    mock_svc.clear.assert_called_once()


# ---------------------------------------------------------------------------
# open_file_from_menu
# ---------------------------------------------------------------------------


@patch("backend.window_manager.open_file")
@patch("backend.window_manager.recent_files_service")
@patch("backend.window_manager.webview")
def test_open_file_adds_to_recent_and_loads(mock_webview, mock_recent_svc, mock_open_file):
    window = MagicMock()
    window.create_file_dialog.return_value = ["/x/diagram.mmd"]
    mock_webview.windows = [window]
    port = 8080

    open_file_from_menu(port)

    mock_recent_svc.add.assert_called_once_with("/x/diagram.mmd")
    mock_open_file.assert_called_once_with("/x/diagram.mmd", port)


@patch("backend.window_manager.open_file")
@patch("backend.window_manager.recent_files_service")
@patch("backend.window_manager.webview")
def test_open_file_cancelled_does_nothing(mock_webview, mock_recent_svc, mock_open_file):
    window = MagicMock()
    window.create_file_dialog.return_value = None
    mock_webview.windows = [window]

    open_file_from_menu(8080)

    mock_recent_svc.add.assert_not_called()
    mock_open_file.assert_not_called()


@patch("backend.window_manager.open_file")
@patch("backend.window_manager.recent_files_service")
@patch("backend.window_manager.webview")
def test_open_file_from_menu_no_windows_does_nothing(mock_webview, mock_recent_svc, mock_open_file):
    mock_webview.windows = []

    open_file_from_menu(8080)

    mock_recent_svc.add.assert_not_called()
    mock_open_file.assert_not_called()
