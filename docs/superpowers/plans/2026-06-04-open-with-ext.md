# open_with_ext Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.mmd` および `.mermaid` ファイルを macOS の「このアプリで開く」から mmdview で開けるようにする。

**Architecture:** `mmdview.spec` に `CFBundleDocumentTypes` を追加して Finder に拡張子を登録し、`backend/apple_events.py` で `NSAppleEventManager` を通じて Apple Events を受け取る。起動時は `sys.argv[1]` でパスを受け取り、起動済みの場合は Apple Events コールバック経由で `watch_service.set_file()` と画面リロードを実行する。

**Tech Stack:** pyobjc-framework-Cocoa (NSAppleEventManager / NSObject), PyInstaller (CFBundleDocumentTypes), Python unittest.mock

---

## ファイル構成

| 対象 | 種別 | 責務 |
|---|---|---|
| `pyproject.toml` | 変更 | `pyobjc-framework-Cocoa` を依存に追加 |
| `backend/apple_events.py` | 新規 | Apple Events ハンドラーの登録と実行 |
| `backend/app.py` | 変更 | `sys.argv` チェック・ハンドラー登録・ダイアログフィルター更新 |
| `mmdview.spec` | 変更 | `CFBundleDocumentTypes` を `info_plist` に追加 |
| `tests/unit/test_apple_events.py` | 新規 | `_OpenFileHandler` のユニットテスト |

---

### Task 1: pyobjc-framework-Cocoa を依存に追加する

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: `pyproject.toml` に依存を追加する**

`dependencies` リストに以下を追加する（`sys_platform` 条件付きで Linux CI に影響させない）:

```toml
[project]
dependencies = [
    "fastapi>=0.136",
    "uvicorn[standard]>=0.46",
    "pywebview>=6.2",
    "watchdog>=6.0",
    "sse-starlette>=2.1",
    "jinja2>=3.1",
    "pyobjc-framework-Cocoa>=10.0; sys_platform == 'darwin'",
]
```

- [ ] **Step 2: `uv lock` を実行してロックファイルを更新する**

```bash
uv lock
```

Expected: `uv.lock` が更新される（エラーなし）

- [ ] **Step 3: インストール確認**

```bash
uv run python -c "from AppKit import NSAppleEventManager; print('OK')"
```

Expected: `OK` と表示される

- [ ] **Step 4: コミット**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: pyobjc-framework-Cocoa を依存に追加する"
```

---

### Task 2: backend/apple_events.py を TDD で実装する

**Files:**
- Create: `backend/apple_events.py`
- Create: `tests/unit/test_apple_events.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# tests/unit/test_apple_events.py
import pytest
from unittest.mock import MagicMock, patch

pytest.importorskip("AppKit")

from backend.apple_events import _OpenFileHandler


def test_handler_calls_callback_with_posix_path():
    received: list[str] = []
    handler = _OpenFileHandler.alloc().init()
    handler._callback = received.append

    mock_url = MagicMock()
    mock_url.path.return_value = "/Users/user/test.mmd"

    mock_desc_item = MagicMock()
    mock_desc_item.stringValue.return_value = "file:///Users/user/test.mmd"

    mock_desc = MagicMock()
    mock_desc.numberOfItems.return_value = 1
    mock_desc.descriptorAtIndex_.return_value = mock_desc_item

    mock_event = MagicMock()
    mock_event.paramDescriptorForKeyword_.return_value = mock_desc

    with patch("backend.apple_events.NSURL") as mock_nsurl:
        mock_nsurl.URLWithString_.return_value = mock_url
        handler.handleOpenDocuments_withReplyEvent_(mock_event, None)

    assert received == ["/Users/user/test.mmd"]


def test_handler_skips_when_path_is_none():
    received: list[str] = []
    handler = _OpenFileHandler.alloc().init()
    handler._callback = received.append

    mock_url = MagicMock()
    mock_url.path.return_value = None  # 不正な URL -> スキップ

    mock_desc_item = MagicMock()
    mock_desc_item.stringValue.return_value = "invalid"

    mock_desc = MagicMock()
    mock_desc.numberOfItems.return_value = 1
    mock_desc.descriptorAtIndex_.return_value = mock_desc_item

    mock_event = MagicMock()
    mock_event.paramDescriptorForKeyword_.return_value = mock_desc

    with patch("backend.apple_events.NSURL") as mock_nsurl:
        mock_nsurl.URLWithString_.return_value = mock_url
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

    def make_desc_item(raw: str) -> MagicMock:
        m = MagicMock()
        m.stringValue.return_value = raw
        return m

    items = [
        make_desc_item("file:///a.mmd"),
        make_desc_item("file:///b.mermaid"),
    ]
    urls = [make_url("/a.mmd"), make_url("/b.mermaid")]

    mock_desc = MagicMock()
    mock_desc.numberOfItems.return_value = 2
    mock_desc.descriptorAtIndex_.side_effect = lambda i: items[i - 1]

    mock_event = MagicMock()
    mock_event.paramDescriptorForKeyword_.return_value = mock_desc

    with patch("backend.apple_events.NSURL") as mock_nsurl:
        mock_nsurl.URLWithString_.side_effect = lambda raw: urls[
            ["file:///a.mmd", "file:///b.mermaid"].index(raw)
        ]
        handler.handleOpenDocuments_withReplyEvent_(mock_event, None)

    assert received == ["/a.mmd", "/b.mermaid"]
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_apple_events.py -v
```

Expected: `ImportError` または `ModuleNotFoundError: No module named 'backend.apple_events'`

- [ ] **Step 3: `backend/apple_events.py` を実装する**

```python
import struct
from collections.abc import Callable

from AppKit import NSAppleEventManager
from Foundation import NSURL, NSObject

_kCoreEventClass = struct.unpack(">I", b"aevt")[0]
_kAEOpenDocuments = struct.unpack(">I", b"odoc")[0]
_keyDirectObject = struct.unpack(">I", b"----")[0]


class _OpenFileHandler(NSObject):
    _callback: Callable[[str], None] | None = None

    def handleOpenDocuments_withReplyEvent_(self, event, reply) -> None:
        desc = event.paramDescriptorForKeyword_(_keyDirectObject)
        for i in range(1, desc.numberOfItems() + 1):
            raw = desc.descriptorAtIndex_(i).stringValue()
            path = NSURL.URLWithString_(raw).path()
            if path and self._callback:
                self._callback(path)


def register_open_file_handler(callback: Callable[[str], None]) -> None:
    handler = _OpenFileHandler.alloc().init()
    handler._callback = callback
    mgr = NSAppleEventManager.sharedAppleEventManager()
    mgr.setEventHandler_andSelector_forEventClass_andEventID_(
        handler,
        "handleOpenDocuments:withReplyEvent:",
        _kCoreEventClass,
        _kAEOpenDocuments,
    )
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/unit/test_apple_events.py -v
```

Expected:
```
tests/unit/test_apple_events.py::test_handler_calls_callback_with_posix_path PASSED
tests/unit/test_apple_events.py::test_handler_skips_when_path_is_none PASSED
tests/unit/test_apple_events.py::test_handler_processes_multiple_files PASSED
```

- [ ] **Step 5: 全テストが通ることを確認する**

```bash
uv run task test
```

Expected: 全テスト PASS、カバレッジ 80% 以上

- [ ] **Step 6: コミット**

```bash
git add backend/apple_events.py tests/unit/test_apple_events.py
git commit -m "feat: Apple Events ハンドラーを追加する"
```

---

### Task 3: backend/app.py を更新する

**Files:**
- Modify: `backend/app.py`

`backend/app.py` はカバレッジ対象外（`pyproject.toml` の `omit` に含まれる）のため手動確認のみ。

- [ ] **Step 1: `main()` に `sys.argv` チェックを追加する**

`main()` 関数の冒頭（`port = _find_free_port()` の前）に以下を追加し、既存の `state.get("last_file")` より CLI 引数を優先する:

変更前:
```python
def main() -> None:
    port = _find_free_port()
    state = _load_window_state()

    if state.get("last_file"):
        watch_service.set_file(state["last_file"])
```

変更後:
```python
def main() -> None:
    import sys

    port = _find_free_port()
    state = _load_window_state()

    initial_file = (sys.argv[1] if len(sys.argv) > 1 else None) or state.get("last_file")
    if initial_file:
        watch_service.set_file(initial_file)
```

- [ ] **Step 2: Apple Events ハンドラーの登録を追加する**

`_wait_for_server(port)` の直後、`window = webview.create_window(...)` の前に追加する:

変更前:
```python
    _wait_for_server(port)

    window = webview.create_window(
```

変更後:
```python
    _wait_for_server(port)

    from backend.apple_events import register_open_file_handler

    def _on_open_file(path: str) -> None:
        watch_service.set_file(path)
        for win in webview.windows:
            win.evaluate_js("window.location.reload()")

    register_open_file_handler(_on_open_file)

    window = webview.create_window(
```

- [ ] **Step 3: ファイルダイアログのフィルターに `.mermaid` を追加する**

`_open_file_from_menu()` 内の `file_types` を更新する:

変更前:
```python
        file_types=("Mermaid files (*.mmd;*.md)", "All files (*.*)"),
```

変更後:
```python
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
```

- [ ] **Step 4: lint と型チェックを実行する**

```bash
uv run task lint && uv run task typecheck
```

Expected: エラーなし（`unresolved-import` の warn は許容）

- [ ] **Step 5: コミット**

```bash
git add backend/app.py
git commit -m "feat: sys.argv とファイルダイアログに .mermaid 対応を追加する"
```

---

### Task 4: mmdview.spec に CFBundleDocumentTypes を追加する

**Files:**
- Modify: `mmdview.spec`

- [ ] **Step 1: `info_plist` に `CFBundleDocumentTypes` を追加する**

変更前:
```python
    info_plist={
        'NSHighResolutionCapable': True,
        "CFBundleShortVersionString": "0.2.2",
    },
```

変更後:
```python
    info_plist={
        'NSHighResolutionCapable': True,
        "CFBundleShortVersionString": "0.2.2",
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Mermaid Diagram',
                'CFBundleTypeExtensions': ['mmd', 'mermaid'],
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Owner',
            }
        ],
    },
```

- [ ] **Step 2: コミット**

```bash
git add mmdview.spec
git commit -m "feat: .mmd と .mermaid の CFBundleDocumentTypes を登録する"
```

---

### Task 5: ビルドして動作確認する

- [ ] **Step 1: アプリをビルドする**

```bash
uv run task build
```

Expected: `dist/mmdview.app` が生成される（エラーなし）

- [ ] **Step 2: `CFBundleDocumentTypes` が Info.plist に含まれることを確認する**

```bash
/usr/libexec/PlistBuddy -c "Print :CFBundleDocumentTypes" dist/mmdview.app/Contents/Info.plist
```

Expected:
```
Array {
    Dict {
        CFBundleTypeExtensions = Array {
            mmd
            mermaid
        }
        CFBundleTypeName = Mermaid Diagram
        CFBundleTypeRole = Viewer
        LSHandlerRank = Owner
    }
}
```

- [ ] **Step 3: Finder に登録する**

```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f dist/mmdview.app
```

Expected: エラーなし（コマンドが終了する）

- [ ] **Step 4: `duti` で確認する（オプション）**

```bash
brew install duti  # 未インストールの場合
duti -x mmd
duti -x mermaid
```

Expected: `com.degino.mmdview` と表示される

- [ ] **Step 5: 動作確認**

1. `dist/mmdview.app` を起動する
2. `.mmd` ファイルを Finder でダブルクリックする → mmdview で開くことを確認
3. 別の `.mermaid` ファイルを Finder でダブルクリックする（アプリ起動済み） → Apple Events 経由で切り替わることを確認
