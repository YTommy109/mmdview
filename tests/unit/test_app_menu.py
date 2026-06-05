from unittest.mock import MagicMock, patch

from webview.menu import Menu, MenuAction, MenuSeparator

from backend.app import _build_open_recent_menu, _open_file_from_menu


def _action_titles(menu: Menu) -> list[str]:
    return [item.title for item in menu.items if isinstance(item, MenuAction)]


def _has_separator(menu: Menu) -> bool:
    return any(isinstance(item, MenuSeparator) for item in menu.items)


# ---------------------------------------------------------------------------
# _build_open_recent_menu
# ---------------------------------------------------------------------------


@patch("backend.app.recent_files_service")
def test_menu_title_is_open_recent(mock_svc):
    mock_svc.get.return_value = []
    menu = _build_open_recent_menu(MagicMock())
    assert menu.title == "Open Recent..."


@patch("backend.app.recent_files_service")
def test_no_recent_files_shows_placeholder(mock_svc):
    mock_svc.get.return_value = []
    menu = _build_open_recent_menu(MagicMock())
    assert _action_titles(menu) == ["No Recent Files"]
    assert not _has_separator(menu)


@patch("backend.app.recent_files_service")
def test_recent_files_appear_as_menu_items(mock_svc):
    mock_svc.get.return_value = ["/a/foo.mmd", "/b/bar.mmd"]
    menu = _build_open_recent_menu(MagicMock())
    titles = _action_titles(menu)
    assert "/a/foo.mmd" in titles
    assert "/b/bar.mmd" in titles


@patch("backend.app.recent_files_service")
def test_recent_files_menu_has_separator_and_clear(mock_svc):
    mock_svc.get.return_value = ["/a/foo.mmd"]
    menu = _build_open_recent_menu(MagicMock())
    assert _has_separator(menu)
    assert "Clear Menu" in _action_titles(menu)


@patch("backend.app.watch_service")
@patch("backend.app.recent_files_service")
def test_clicking_recent_file_opens_it(mock_recent_svc, mock_watch_svc):
    path = "/a/foo.mmd"
    mock_recent_svc.get.return_value = [path]
    window = MagicMock()

    menu = _build_open_recent_menu(window)

    file_action = next(
        item for item in menu.items if isinstance(item, MenuAction) and item.title == path
    )
    file_action.function()

    mock_recent_svc.add.assert_called_once_with(path)
    mock_watch_svc.set_file.assert_called_once_with(path)
    window.evaluate_js.assert_called_once_with("window.location.reload()")


@patch("backend.app.recent_files_service")
def test_clear_menu_action_calls_clear(mock_svc):
    mock_svc.get.return_value = ["/a/foo.mmd"]
    menu = _build_open_recent_menu(MagicMock())

    clear_action = next(
        item for item in menu.items if isinstance(item, MenuAction) and item.title == "Clear Menu"
    )
    clear_action.function()

    mock_svc.clear.assert_called_once()


# ---------------------------------------------------------------------------
# _open_file_from_menu
# ---------------------------------------------------------------------------


@patch("backend.app.watch_service")
@patch("backend.app.recent_files_service")
def test_open_file_adds_to_recent_and_loads(mock_recent_svc, mock_watch_svc):
    window = MagicMock()
    window.create_file_dialog.return_value = ["/x/diagram.mmd"]

    _open_file_from_menu(window)

    mock_recent_svc.add.assert_called_once_with("/x/diagram.mmd")
    mock_watch_svc.set_file.assert_called_once_with("/x/diagram.mmd")
    window.evaluate_js.assert_called_once_with("window.location.reload()")


@patch("backend.app.watch_service")
@patch("backend.app.recent_files_service")
def test_open_file_cancelled_does_nothing(mock_recent_svc, mock_watch_svc):
    window = MagicMock()
    window.create_file_dialog.return_value = None

    _open_file_from_menu(window)

    mock_recent_svc.add.assert_not_called()
    mock_watch_svc.set_file.assert_not_called()
    window.evaluate_js.assert_not_called()
