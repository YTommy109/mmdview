from unittest.mock import MagicMock

import pytest

pytest.importorskip("AppKit")

from backend.apple_events import _OpenFileHandler


def test_handler_calls_callback_with_posix_path():
    received: list[str] = []
    handler = _OpenFileHandler.alloc().init()
    handler._callback = received.append

    mock_url = MagicMock()
    mock_url.path.return_value = "/Users/user/test.mmd"

    mock_desc_item = MagicMock()
    mock_desc_item.fileURLValue.return_value = mock_url

    mock_desc = MagicMock()
    mock_desc.numberOfItems.return_value = 1
    mock_desc.descriptorAtIndex_.return_value = mock_desc_item

    mock_event = MagicMock()
    mock_event.paramDescriptorForKeyword_.return_value = mock_desc

    handler.handleOpenDocuments_withReplyEvent_(mock_event, None)

    assert received == ["/Users/user/test.mmd"]


def test_handler_skips_when_file_url_is_none():
    received: list[str] = []
    handler = _OpenFileHandler.alloc().init()
    handler._callback = received.append

    mock_desc_item = MagicMock()
    mock_desc_item.fileURLValue.return_value = None  # fileURLValue が None -> スキップ

    mock_desc = MagicMock()
    mock_desc.numberOfItems.return_value = 1
    mock_desc.descriptorAtIndex_.return_value = mock_desc_item

    mock_event = MagicMock()
    mock_event.paramDescriptorForKeyword_.return_value = mock_desc

    handler.handleOpenDocuments_withReplyEvent_(mock_event, None)

    assert received == []


def test_handler_processes_multiple_files():
    received: list[str] = []
    handler = _OpenFileHandler.alloc().init()
    handler._callback = received.append

    def make_url(path: str) -> MagicMock:
        m = MagicMock()
        m.path.return_value = path
        return m

    urls = [make_url("/a.mmd"), make_url("/b.mermaid")]

    def make_desc_item(url: MagicMock) -> MagicMock:
        m = MagicMock()
        m.fileURLValue.return_value = url
        return m

    items = [make_desc_item(urls[0]), make_desc_item(urls[1])]

    mock_desc = MagicMock()
    mock_desc.numberOfItems.return_value = 2
    mock_desc.descriptorAtIndex_.side_effect = lambda i: items[i - 1]

    mock_event = MagicMock()
    mock_event.paramDescriptorForKeyword_.return_value = mock_desc

    handler.handleOpenDocuments_withReplyEvent_(mock_event, None)

    assert received == ["/a.mmd", "/b.mermaid"]
