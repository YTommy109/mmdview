from unittest.mock import MagicMock

from backend.update_window import _reposition_file_menu


def _make_menu(*titles: str) -> MagicMock:
    """タイトルのリストから NSMenu モックを作成する。"""
    items = [MagicMock() for _ in titles]
    for item, title in zip(items, titles):
        item.title.return_value = title

    menu = MagicMock()
    menu.numberOfItems.return_value = len(items)
    menu.itemAtIndex_.side_effect = lambda i: items[i]
    return menu


def test_file_menu_moved_from_end_to_index_1():
    # App(0) → Edit(1) → View(2) → File(3) という pywebview デフォルト順
    menu = _make_menu("App", "Edit", "View", "File")
    file_item = menu.itemAtIndex_(3)

    _reposition_file_menu(menu)

    menu.removeItem_.assert_called_once_with(file_item)
    menu.insertItem_atIndex_.assert_called_once_with(file_item, 1)


def test_file_menu_already_at_index_1_no_move():
    # すでに正しい位置にある場合は何もしない
    menu = _make_menu("App", "File", "Edit", "View")

    _reposition_file_menu(menu)

    menu.removeItem_.assert_not_called()
    menu.insertItem_atIndex_.assert_not_called()


def test_no_file_menu_does_nothing():
    menu = _make_menu("App", "Edit", "View")

    _reposition_file_menu(menu)

    menu.removeItem_.assert_not_called()
    menu.insertItem_atIndex_.assert_not_called()


def test_file_menu_at_index_2_moved_to_1():
    menu = _make_menu("App", "Edit", "File")
    file_item = menu.itemAtIndex_(2)

    _reposition_file_menu(menu)

    menu.removeItem_.assert_called_once_with(file_item)
    menu.insertItem_atIndex_.assert_called_once_with(file_item, 1)
