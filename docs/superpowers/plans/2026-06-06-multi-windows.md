# 複数ウィンドウ対応 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** pywebview + FastAPI で複数の .mmd ファイルを同時に別ウィンドウで表示できるようにする。

**Architecture:** 1つの FastAPI サーバーを全ウィンドウで共有し、各ウィンドウを UUID (`window_id`) で識別する。新規モジュール `WindowRegistry` が `window_id → (WatchService, EventBus)` のマッピングを管理する。各ウィンドウは `/?window_id=X` を読み込み、SSE は `/events?window_id=X` で受信する。

**Tech Stack:** Python 3.12+, FastAPI, pywebview, watchdog, sse-starlette, pytest, uv

---

## ファイル構成

| アクション | ファイル | 役割 |
|---|---|---|
| **新規作成** | `backend/services/window_registry.py` | window_id → WatchService/EventBus のマッピング |
| **新規作成** | `tests/unit/test_window_registry.py` | WindowRegistry のユニットテスト |
| **変更** | `backend/routers/html.py` | `window_id` クエリパラメータ対応 |
| **変更** | `tests/integration/test_html_router.py` | window_registry 経由に更新 |
| **変更** | `backend/routers/events.py` | `window_id` クエリパラメータ対応 |
| **変更** | `backend/templates/viewer.html` | SSE URL に `window_id` を付与 |
| **変更** | `backend/main.py` | lifespan で `window_registry.set_loop()` を呼ぶ |
| **変更** | `backend/app.py` | 複数ウィンドウ管理に全面書き換え |
| **変更** | `backend/services/watch_service.py` | グローバルシングルトン削除、デフォルト変更 |
| **変更** | `backend/services/event_bus.py` | グローバルシングルトン削除 |
| **変更** | `tests/unit/test_window_state.py` | 新しいリスト形式に対応 |

---

### Task 1: WindowRegistry を作成する

**Files:**
- Create: `backend/services/window_registry.py`
- Create: `tests/unit/test_window_registry.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
# tests/unit/test_window_registry.py
import pytest
from pathlib import Path


def _make_registry():
    from backend.services.window_registry import WindowRegistry
    return WindowRegistry()


def test_get_watch_returns_none_for_unknown():
    r = _make_registry()
    assert r.get_watch("nonexistent") is None


def test_get_bus_returns_none_for_unknown():
    r = _make_registry()
    assert r.get_bus("nonexistent") is None


def test_create_registers_watch_and_bus():
    r = _make_registry()
    r.create("w1")
    assert r.get_watch("w1") is not None
    assert r.get_bus("w1") is not None
    r.remove("w1")


def test_remove_stops_watch_and_clears_entry(tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A-->B")
    r = _make_registry()
    r.create("w1", str(f))
    watch = r.get_watch("w1")
    r.remove("w1")
    assert watch._observer is None
    assert r.get_watch("w1") is None


def test_find_by_path_returns_none_when_not_registered():
    r = _make_registry()
    r.create("w1")
    assert r.find_by_path("/nonexistent/file.mmd") is None
    r.remove("w1")


def test_find_by_path_returns_window_id(tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD")
    r = _make_registry()
    r.create("w1", str(f))
    assert r.find_by_path(str(f)) == "w1"
    r.remove("w1")


def test_snapshot_returns_all_window_ids_and_paths(tmp_path):
    f1 = tmp_path / "a.mmd"
    f1.write_text("graph TD")
    f2 = tmp_path / "b.mmd"
    f2.write_text("graph TD")
    r = _make_registry()
    r.create("w1", str(f1))
    r.create("w2", str(f2))
    snap = dict(r.snapshot())
    assert snap["w1"] == f1
    assert snap["w2"] == f2
    r.remove("w1")
    r.remove("w2")


def test_set_path_updates_find_by_path(tmp_path):
    f1 = tmp_path / "a.mmd"
    f1.write_text("graph TD")
    f2 = tmp_path / "b.mmd"
    f2.write_text("graph TD")
    r = _make_registry()
    r.create("w1", str(f1))
    r.set_path("w1", str(f2))
    assert r.find_by_path(str(f2)) == "w1"
    assert r.find_by_path(str(f1)) is None
    r.remove("w1")
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_window_registry.py -v
```

期待: `ModuleNotFoundError: No module named 'backend.services.window_registry'`

- [ ] **Step 3: WindowRegistry を実装する**

```python
# backend/services/window_registry.py
import asyncio
from pathlib import Path

from backend.services.event_bus import EventBus
from backend.services.watch_service import WatchService


class WindowRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, dict] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def create(self, window_id: str, file_path: str | None = None) -> None:
        bus = EventBus()
        if self._loop is not None:
            bus.set_loop(self._loop)
        watch = WatchService(event_bus=bus)
        if file_path:
            watch.set_file(file_path)
        self._entries[window_id] = {
            "watch": watch,
            "bus": bus,
            "path": Path(file_path) if file_path else None,
        }

    def get_watch(self, window_id: str) -> WatchService | None:
        entry = self._entries.get(window_id)
        return entry["watch"] if entry else None

    def get_bus(self, window_id: str) -> EventBus | None:
        entry = self._entries.get(window_id)
        return entry["bus"] if entry else None

    def remove(self, window_id: str) -> None:
        entry = self._entries.pop(window_id, None)
        if entry:
            entry["watch"].stop()

    def find_by_path(self, path: str) -> str | None:
        p = Path(path)
        for wid, entry in self._entries.items():
            if entry["path"] == p:
                return wid
        return None

    def set_path(self, window_id: str, path: str) -> None:
        entry = self._entries.get(window_id)
        if entry:
            entry["path"] = Path(path)

    def snapshot(self) -> list[tuple[str, Path | None]]:
        return [(wid, entry["path"]) for wid, entry in self._entries.items()]


window_registry = WindowRegistry()
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/unit/test_window_registry.py -v
```

期待: 8 passed

- [ ] **Step 5: コミットする**

```bash
git add backend/services/window_registry.py tests/unit/test_window_registry.py
git commit -m "feat: WindowRegistry を追加する"
```

---

### Task 2: html.py を window_id パラメータ対応にする

**Files:**
- Modify: `backend/routers/html.py`
- Modify: `tests/integration/test_html_router.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/integration/test_html_router.py` を以下で置き換える:

```python
import pytest


@pytest.fixture(autouse=True)
def cleanup_registry():
    yield
    from backend.services.window_registry import window_registry
    for wid, _ in list(window_registry.snapshot()):
        window_registry.remove(wid)


def test_index_shows_welcome_when_no_window_id(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "File → Open..." in response.text


def test_index_shows_welcome_for_unknown_window_id(client):
    response = client.get("/?window_id=unknown-id")
    assert response.status_code == 200
    assert "File → Open..." in response.text


def test_index_shows_viewer_when_file_registered(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry
    window_registry.create("w1", str(f))

    response = client.get("/?window_id=w1")
    assert response.status_code == 200
    assert "graph TD" in response.text
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待: `test_index_shows_welcome_for_unknown_window_id` と `test_index_shows_viewer_when_file_registered` が FAIL

- [ ] **Step 3: html.py を実装する**

```python
# backend/routers/html.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.paths import TEMPLATES_DIR
from backend.services.window_registry import window_registry

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, window_id: str = "") -> HTMLResponse:
    watch = window_registry.get_watch(window_id)
    if watch is None:
        return templates.TemplateResponse(request, "welcome.html")
    content = watch.get_content()
    path = watch.get_path()
    if content is None or path is None:
        return templates.TemplateResponse(request, "welcome.html")
    return templates.TemplateResponse(
        request,
        "viewer.html",
        {"content": content},
    )
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待: 3 passed

- [ ] **Step 5: 全テストがグリーンであることを確認する**

```bash
uv run pytest -v
```

期待: 全テスト passed（カバレッジ警告は無視してよい）

- [ ] **Step 6: コミットする**

```bash
git add backend/routers/html.py tests/integration/test_html_router.py
git commit -m "feat: html router に window_id クエリパラメータを追加する"
```

---

### Task 3: events.py を window_id パラメータ対応にする

**Files:**
- Modify: `backend/routers/events.py`

- [ ] **Step 1: events.py を実装する**

```python
# backend/routers/events.py
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from backend.services.window_registry import window_registry

router = APIRouter()


@router.get("/events")
async def sse_endpoint(request: Request, window_id: str = "") -> EventSourceResponse:
    async def generator():
        bus = window_registry.get_bus(window_id)
        if bus is None:
            return
        q = bus.subscribe()
        try:
            while True:
                event = await q.get()
                yield {"data": event}
        finally:
            bus.unsubscribe(q)

    return EventSourceResponse(generator())
```

- [ ] **Step 2: 全テストがグリーンであることを確認する**

```bash
uv run pytest -v
```

期待: 全テスト passed

- [ ] **Step 3: コミットする**

```bash
git add backend/routers/events.py
git commit -m "feat: events router に window_id クエリパラメータを追加する"
```

---

### Task 4: viewer.html の SSE URL に window_id を付与する

**Files:**
- Modify: `backend/templates/viewer.html`

現在の `viewer.html` は `/events` をハードコードしている。ウィンドウ固有の SSE チャンネルに接続するため、ページの URL パラメータから `window_id` を取得して付与する。

- [ ] **Step 1: viewer.html を更新する**

`backend/templates/viewer.html` の以下の行:
```javascript
  const evtSource = new EventSource('/events');
```
を以下に変更する:
```javascript
  const wid = new URLSearchParams(window.location.search).get('window_id') || '';
  const evtSource = new EventSource('/events?window_id=' + encodeURIComponent(wid));
```

変更後の `viewer.html` 全体:
```html
{% extends "base.html" %}
{% block content %}
<div class="viewer">
  <pre class="mermaid">{{ content }}</pre>
</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({
    startOnLoad: true,
    theme: 'default',
    sequence: { useMaxWidth: false },
    er: { useMaxWidth: false },
    flowchart: { useMaxWidth: false },
    gantt: { useMaxWidth: false },
    journey: { useMaxWidth: false },
    pie: { useMaxWidth: false },
    state: { useMaxWidth: false },
    class: { useMaxWidth: false },
  });

  const wid = new URLSearchParams(window.location.search).get('window_id') || '';
  const evtSource = new EventSource('/events?window_id=' + encodeURIComponent(wid));
  evtSource.onmessage = (e) => {
    if (e.data === 'reload') window.location.reload();
  };
</script>
{% endblock %}
```

- [ ] **Step 2: 全テストがグリーンであることを確認する**

```bash
uv run pytest -v
```

- [ ] **Step 3: コミットする**

```bash
git add backend/templates/viewer.html
git commit -m "feat: viewer の SSE 接続に window_id を付与する"
```

---

### Task 5: main.py の lifespan を window_registry 対応にする

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1: main.py を更新する**

```python
# backend/main.py
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.paths import STATIC_DIR
from backend.routers import events, html, update
from backend.services.window_registry import window_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    window_registry.set_loop(asyncio.get_event_loop())
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(html.router)
app.include_router(events.router)
app.include_router(update.router)
```

- [ ] **Step 2: 全テストがグリーンであることを確認する**

```bash
uv run pytest -v
```

- [ ] **Step 3: コミットする**

```bash
git add backend/main.py
git commit -m "feat: lifespan で window_registry にイベントループを設定する"
```

---

### Task 6: app.py を複数ウィンドウ管理に書き換える

**Files:**
- Modify: `backend/app.py`

`app.py` はテストカバレッジ対象外（`pyproject.toml` の `coverage.omit` に含まれる）。

設計方針:
- モジュールレベルの `_windows: dict[str, webview.Window] = {}` で window_id → Window を管理
- `_create_window()` が window_id を生成し、registry へ登録して webview.Window を作成する
- `_open_file()` が重複チェックし、既存ウィンドウをフォーカスするか新規作成するかを決定する
- `_load_window_states()` が JSON リスト形式で読み込む（旧辞書形式に後方互換あり）
- `_save_all_states()` が全ウィンドウの状態をリストで保存する

- [ ] **Step 1: app.py を書き換える**

```python
# backend/app.py
import json
import socket
import sys
import threading
import traceback
from pathlib import Path
from uuid import uuid4

import webview
from webview import FileDialog
from webview.menu import Menu, MenuAction, MenuSeparator

from backend.logger import logger
from backend.main import app
from backend.paths import WINDOW_STATE_FILE
from backend.services.recent_files_service import recent_files_service
from backend.services.window_registry import window_registry

import uvicorn

# window_id → webview.Window の対応表
_windows: dict[str, webview.Window] = {}


def _load_window_states() -> list[dict]:
    """保存済みウィンドウ状態をリストで返す。ファイルがなければ空リスト。"""
    if WINDOW_STATE_FILE.exists():
        try:
            data = json.loads(WINDOW_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # 旧形式（シングルウィンドウ）に後方互換
                return [{
                    "x": data.get("x", 100),
                    "y": data.get("y", 100),
                    "width": data.get("width", 1024),
                    "height": data.get("height", 768),
                    "file": data.get("last_file"),
                }]
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    return []


def _save_all_states() -> None:
    """全ウィンドウの状態を JSON リストとして保存する。"""
    states = []
    for wid, win in list(_windows.items()):
        watch = window_registry.get_watch(wid)
        path = watch.get_path() if watch else None
        states.append({
            "x": win.x,
            "y": win.y,
            "width": win.width,
            "height": win.height,
            "file": str(path) if path else None,
        })
    try:
        WINDOW_STATE_FILE.write_text(json.dumps(states), encoding="utf-8")
    except OSError:
        logger.error("_save_all_states: 書き込み失敗\n%s", traceback.format_exc())


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int) -> None:
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


def _wait_for_server(port: int, timeout: float = 5.0) -> None:
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"Server did not start on port {port} within {timeout}s")


def _focus_window(window: webview.Window) -> None:
    """ウィンドウをフロントに持ってくるベストエフォート実装。"""
    try:
        window.evaluate_js("window.focus()")
        if sys.platform == "darwin":
            from AppKit import NSApp  # type: ignore[import]
            NSApp.activateIgnoringOtherApps_(True)
    except Exception:
        pass


def _create_window(
    port: int,
    file_path: str | None = None,
    x: int = 100,
    y: int = 100,
    width: int = 1024,
    height: int = 768,
) -> tuple[str, webview.Window]:
    """新しいウィンドウを作成し、registry と _windows に登録して返す。"""
    window_id = str(uuid4())
    window_registry.create(window_id, file_path)

    title = Path(file_path).name if file_path else "mmdview"
    window = webview.create_window(
        title,
        f"http://127.0.0.1:{port}/?window_id={window_id}",
        x=x,
        y=y,
        width=width,
        height=height,
    )
    assert window is not None
    _windows[window_id] = window

    # 各ウィンドウが自分用の debounce タイマーを持つ
    _save_timer: threading.Timer | None = None

    def _schedule_save() -> None:
        nonlocal _save_timer
        if _save_timer:
            _save_timer.cancel()
        _save_timer = threading.Timer(0.5, _save_all_states)
        _save_timer.start()

    window.events.moved += lambda x, y: _schedule_save()
    window.events.resized += lambda width, height: _schedule_save()

    def _on_closed() -> None:
        _windows.pop(window_id, None)
        window_registry.remove(window_id)
        _save_all_states()

    window.events.closed += _on_closed
    return window_id, window


def _open_file(path: str, port: int) -> None:
    """ファイルを開く。既に開いていれば既存ウィンドウをフォーカスし、なければ新規作成。"""
    existing_id = window_registry.find_by_path(path)
    if existing_id and existing_id in _windows:
        logger.info("_open_file: already open, focusing: %s", path)
        _focus_window(_windows[existing_id])
        return
    logger.info("_open_file: opening new window: %s", path)
    _create_window(port, file_path=path)


def _open_file_from_menu(port: int) -> None:
    if not webview.windows:
        return
    result = webview.windows[0].create_file_dialog(
        FileDialog.OPEN,
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    if result:
        recent_files_service.add(result[0])
        _open_file(result[0], port)


def _build_open_recent_menu(port: int) -> Menu:
    recent = recent_files_service.get()

    def _open_recent(path: str) -> None:
        recent_files_service.add(path)
        _open_file(path, port)

    if recent:
        items: list = [MenuAction(p, lambda p=p: _open_recent(p)) for p in recent]
        items += [MenuSeparator(), MenuAction("Clear Menu", recent_files_service.clear)]
    else:
        items = [MenuAction("No Recent Files", lambda: None)]

    return Menu("Open Recent...", items)


def _patch_app_delegate_for_open_file(callback) -> None:
    """NSApp.finishLaunching() が odoc ハンドラを上書きするため、
    applicationDidFinishLaunching_ で再登録するようにパッチを当てる。"""
    if sys.platform != "darwin":
        return
    try:
        from webview.platforms import cocoa as _cocoa  # type: ignore[import]
        from backend.apple_events import register_open_file_handler

        def _did_finish_launching(self: object, notification: object) -> None:
            register_open_file_handler(callback)

        _cocoa.BrowserView.AppDelegate.applicationDidFinishLaunching_ = _did_finish_launching
    except Exception:
        logger.warning("applicationDidFinishLaunching_ パッチに失敗しました")


def main() -> None:
    from backend.version import __version__
    logger.info("mmdview %s starting: argv=%s", __version__, sys.argv)

    port = _find_free_port()

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()
    _wait_for_server(port)

    def _on_open_file(path: str) -> None:
        logger.info("_on_open_file called: path=%s", path)
        try:
            recent_files_service.add(path)
            _open_file(path, port)
        except Exception:
            logger.error("_on_open_file failed: path=%s\n%s", path, traceback.format_exc())

    # 初期ウィンドウの決定
    if len(sys.argv) > 1:
        cli_file = sys.argv[1]
        recent_files_service.add(cli_file)
        _create_window(port, file_path=cli_file)
    else:
        states = _load_window_states()
        if states:
            for s in states:
                _create_window(
                    port,
                    file_path=s.get("file"),
                    x=s.get("x", 100),
                    y=s.get("y", 100),
                    width=s.get("width", 1024),
                    height=s.get("height", 768),
                )
        else:
            _create_window(port)

    menu = [
        Menu(
            "File",
            [
                MenuAction("Open...", lambda: _open_file_from_menu(port)),
                _build_open_recent_menu(port),
            ],
        )
    ]

    from backend.apple_events import register_open_file_handler
    from backend.update_window import setup_app_menu

    register_open_file_handler(_on_open_file)
    _patch_app_delegate_for_open_file(_on_open_file)

    def _on_webview_ready() -> None:
        setup_app_menu(port)

    webview.start(menu=menu, func=_on_webview_ready)

    # アプリ終了時に全ウィンドウをクリーンアップ
    for wid, _ in window_registry.snapshot():
        window_registry.remove(wid)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 全テストがグリーンであることを確認する**

```bash
uv run pytest -v
```

期待: 全テスト passed

- [ ] **Step 3: コミットする**

```bash
git add backend/app.py
git commit -m "feat: app.py を複数ウィンドウ管理に書き換える"
```

---

### Task 7: グローバルシングルトンを削除する

**Files:**
- Modify: `backend/services/watch_service.py`
- Modify: `backend/services/event_bus.py`

Task 6 完了後、`watch_service` と `event_bus` のグローバルシングルトンはどこからも使われなくなる。

- [ ] **Step 1: watch_service.py からグローバルシングルトンを削除する**

`backend/services/watch_service.py` を以下で置き換える:

```python
# backend/services/watch_service.py
import traceback
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.logger import logger
from backend.services.event_bus import EventBus


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, target: Path, bus: EventBus) -> None:
        self._target = target
        self._bus = bus

    def on_modified(self, event: FileSystemEvent) -> None:
        src = event.src_path
        if isinstance(src, bytes):
            src = src.decode()
        if Path(src) == self._target:
            self._bus.notify()


class WatchService:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus if event_bus is not None else EventBus()
        self._observer: Any = None
        self._path: Path | None = None

    def set_file(self, path: str) -> None:
        logger.info("set_file: path=%s", path)
        self.stop()
        self._path = Path(path)
        if not self._path.exists():
            logger.error("set_file: file not found: %s", self._path)
        observer = Observer()
        handler = _ChangeHandler(self._path, self._bus)
        observer.schedule(handler, str(self._path.parent), recursive=False)
        try:
            observer.start()
        except Exception:
            logger.error("set_file: observer.start() failed:\n%s", traceback.format_exc())
            raise
        self._observer = observer
        logger.info("set_file: watching %s", self._path)

    def get_content(self) -> str | None:
        if self._path is None or not self._path.exists():
            return None
        return self._path.read_text(encoding="utf-8")

    def get_path(self) -> Path | None:
        return self._path

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
```

- [ ] **Step 2: event_bus.py からグローバルシングルトンを削除する**

`backend/services/event_bus.py` の末尾の `event_bus = EventBus()` の行を削除する。

変更後の `event_bus.py` 全体:

```python
# backend/services/event_bus.py
import asyncio


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    def notify(self, event: str = "reload") -> None:
        if self._loop is None:
            return
        for q in list(self._listeners):
            self._loop.call_soon_threadsafe(q.put_nowait, event)
```

- [ ] **Step 3: 全テストがグリーンであることを確認する**

```bash
uv run pytest -v
```

期待: 全テスト passed

- [ ] **Step 4: コミットする**

```bash
git add backend/services/watch_service.py backend/services/event_bus.py
git commit -m "refactor: watch_service と event_bus のグローバルシングルトンを削除する"
```

---

### Task 8: test_window_state.py を新しいフォーマットに更新する

**Files:**
- Modify: `tests/unit/test_window_state.py`

`app.py` の `_load_window_state` が `_load_window_states`（リスト返し）に変わった。

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_window_state.py` を以下で置き換える:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_load_window_states_returns_empty_list_when_file_missing():
    import backend.app as app_module

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = False

    with patch.object(app_module, "WINDOW_STATE_FILE", fake_path):
        result = app_module._load_window_states()

    assert result == []


def test_load_window_states_returns_empty_list_on_oserror():
    import backend.app as app_module

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = True
    fake_path.read_text.side_effect = OSError("Permission denied")

    with patch.object(app_module, "WINDOW_STATE_FILE", fake_path):
        result = app_module._load_window_states()

    assert result == []


def test_load_window_states_returns_list_format(tmp_path):
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


def test_load_window_states_converts_old_dict_format(tmp_path):
    """旧フォーマット（辞書）を読み込んだ場合、1要素のリストに変換する。"""
    import json
    import backend.app as app_module

    state_file = tmp_path / "window_state.json"
    old_state = {"x": 100, "y": 100, "width": 1024, "height": 768, "last_file": "/old/file.mmd"}
    state_file.write_text(json.dumps(old_state), encoding="utf-8")

    with patch.object(app_module, "WINDOW_STATE_FILE", state_file):
        result = app_module._load_window_states()

    assert len(result) == 1
    assert result[0]["file"] == "/old/file.mmd"
    assert result[0]["x"] == 100
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/unit/test_window_state.py -v
```

期待: `AttributeError: module 'backend.app' has no attribute '_load_window_states'`（Task 6 完了後は AttributeError、未完了なら旧テストが通る）

- [ ] **Step 3: テストが通ることを確認する（Task 6 完了後）**

```bash
uv run pytest tests/unit/test_window_state.py -v
```

期待: 4 passed

- [ ] **Step 4: 全テストとカバレッジが通ることを確認する**

```bash
uv run pytest -v --cov --cov-report=term-missing
```

期待: 全テスト passed、カバレッジ 80% 以上

- [ ] **Step 5: コミットする**

```bash
git add tests/unit/test_window_state.py
git commit -m "test: test_window_state を新しいリスト形式に対応させる"
```

---

## 動作確認チェックリスト

実装完了後に手動で確認する:

- [ ] `uv run task dev` でアプリが起動する
- [ ] Finder から .mmd ファイルをダブルクリックすると新しいウィンドウが開く
- [ ] 同じファイルを再度ダブルクリックすると新しいウィンドウは開かない（既存にフォーカス）
- [ ] File → Open... で別のファイルを選ぶと新しいウィンドウで開く
- [ ] ファイルを変更・保存するとそのウィンドウだけリロードされる（他ウィンドウには影響しない）
- [ ] アプリを終了して再起動すると、前回開いていたウィンドウが全て復元される
- [ ] `mmdview file.mmd` を CLI で実行すると新しいウィンドウが開く
