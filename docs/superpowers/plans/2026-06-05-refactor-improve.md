# mmdview 改善計画 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** バグ修正（C1/C3/C4/C5）・ファイル開く処理の統一・スレッド安全性修正（C6/C7）を 4 コミットで段階的に実装する。

**Architecture:** `_activate_file()` ヘルパーを抽出して 3 つのファイル開く経路を統一し、`html.py` の `/open-file` エンドポイントも同じ invariant（recent_files への追加）を満たすように修正する。スレッド安全性は `threading.Lock` とリストスナップショットで対処する。

**Tech Stack:** Python 3.12, FastAPI, pywebview, watchdog, pytest, unittest.mock

---

## ファイルマップ

| ファイル | 変更種別 | 担当タスク |
|----------|----------|-----------|
| `backend/app.py` | 修正 | Task 1 (例外), Task 3 (_activate_file), Task 4 (起動時) |
| `backend/routers/html.py` | 修正 | Task 2 (recent_files + filter) |
| `backend/update_window.py` | 修正 | Task 5 (lock) |
| `backend/services/event_bus.py` | 修正 | Task 6 (snapshot) |
| `tests/unit/test_window_state.py` | 新規 | Task 1 |
| `tests/integration/test_html_router.py` | 修正 | Task 2 |
| `tests/unit/test_update_window.py` | 修正 | Task 5 |
| `tests/unit/test_event_bus.py` | 修正 | Task 6 |

---

## Task 1: C5 — `_load_window_state` の OSError 捕捉

**Files:**
- Modify: `backend/app.py:26`
- Create: `tests/unit/test_window_state.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/unit/test_window_state.py` を新規作成:

```python
from unittest.mock import MagicMock, patch
from pathlib import Path


def test_load_window_state_returns_default_on_oserror():
    """WINDOW_STATE_FILE が存在するが read_text() が OSError を投げる場合、
    デフォルト値を返すことを確認する。"""
    import backend.app as app_module

    fake_path = MagicMock(spec=Path)
    fake_path.exists.return_value = True
    fake_path.read_text.side_effect = OSError("Permission denied")

    with patch.object(app_module, "WINDOW_STATE_FILE", fake_path):
        result = app_module._load_window_state()

    assert result == {"x": 100, "y": 100, "width": 1024, "height": 768, "last_file": None}
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/unit/test_window_state.py -v
```

期待: `FAILED` — `OSError: Permission denied` が伝播して `_load_window_state` がクラッシュする。

- [ ] **Step 3: `backend/app.py` の except 句を修正**

`backend/app.py:26` を以下のように変更:

```python
# 変更前
        except (json.JSONDecodeError, KeyError):

# 変更後
        except (json.JSONDecodeError, KeyError, OSError):
```

- [ ] **Step 4: テストを実行してパスを確認**

```bash
uv run pytest tests/unit/test_window_state.py -v
```

期待: `PASSED`

- [ ] **Step 5: 全テストを実行してリグレッションがないことを確認**

```bash
uv run pytest -v --tb=short
```

期待: 全テストがパス。

- [ ] **Step 6: コミット**

```bash
git add backend/app.py tests/unit/test_window_state.py
git commit -m "fix: _load_window_state で OSError を捕捉してデフォルト値を返す"
```

---

## Task 2: C1/C3 — `/open-file` の recent_files 追加とファイルタイプフィルタ修正

**Files:**
- Modify: `backend/routers/html.py`
- Modify: `tests/integration/test_html_router.py`

### Step 1: 失敗するテストを追加

`tests/integration/test_html_router.py` に以下を追加する（既存コードの末尾に追記）:

```python
# ファイル先頭の import を以下に更新（patch は既存、MagicMock を追加）
from unittest.mock import MagicMock, patch


@patch("backend.routers.html.recent_files_service")
def test_open_file_adds_to_recent_files(mock_recent_svc, client, tmp_path):
    """POST /open-file はファイルを recent_files_service に追加しなければならない。"""
    f = tmp_path / "diagram.mmd"
    f.write_text("graph LR\n    X --> Y", encoding="utf-8")

    with patch("backend.routers.html._pick_file", return_value=str(f)):
        response = client.post("/open-file")

    assert response.status_code == 200
    mock_recent_svc.add.assert_called_once_with(str(f))


def test_pick_file_uses_mermaid_extension():
    """_pick_file() のファイルタイプフィルタは *.mermaid を使い *.md は使わない。"""
    import webview

    mock_window = MagicMock()
    mock_window.create_file_dialog.return_value = None

    with patch.object(webview, "windows", [mock_window]):
        from backend.routers.html import _pick_file
        _pick_file()

    file_types_str = mock_window.create_file_dialog.call_args.kwargs["file_types"][0]
    assert "*.mermaid" in file_types_str, f"Expected *.mermaid in filter, got: {file_types_str}"
    assert "*.md" not in file_types_str, f"*.md should not be in Mermaid filter, got: {file_types_str}"
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/integration/test_html_router.py::test_open_file_adds_to_recent_files tests/integration/test_html_router.py::test_pick_file_uses_mermaid_extension -v
```

期待:
- `test_open_file_adds_to_recent_files`: `AttributeError: module 'backend.routers.html' has no attribute 'recent_files_service'`
- `test_pick_file_uses_mermaid_extension`: `AssertionError: Expected *.mermaid in filter`

- [ ] **Step 3: `backend/routers/html.py` を修正**

`backend/routers/html.py` を以下の内容に置き換える:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from backend.paths import TEMPLATES_DIR
from backend.services.recent_files_service import recent_files_service
from backend.services.watch_service import watch_service

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _pick_file() -> str | None:
    import webview
    from webview import FileDialog

    result = webview.windows[0].create_file_dialog(
        FileDialog.OPEN,
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    return result[0] if result else None


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    content = watch_service.get_content()
    path = watch_service.get_path()
    if content is None or path is None:
        return templates.TemplateResponse(request, "welcome.html")
    return templates.TemplateResponse(
        request,
        "viewer.html",
        {
            "content": content,
            "filename": path.name,
            "filepath": str(path),
        },
    )


@router.post("/open-file")
async def open_file() -> Response:
    path = _pick_file()
    if path:
        recent_files_service.add(path)
        watch_service.set_file(path)
    return Response(headers={"HX-Redirect": "/"})
```

- [ ] **Step 4: テストを実行してパスを確認**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待: 全テストがパス。

- [ ] **Step 5: 全テストを実行してリグレッションがないことを確認**

```bash
uv run pytest -v --tb=short
```

期待: 全テストがパス。

- [ ] **Step 6: コミット（後の Task 3/4 と同じコミットにまとめるため、ここではまだコミットしない）**

> Task 4 完了後にまとめてコミットする。

---

## Task 3: リファクタリング — `_activate_file` ヘルパー抽出

**Files:**
- Modify: `backend/app.py`

このタスクは振る舞いを変えない純粋なリファクタリング。既存テストがリグレッションの検出器になる。

- [ ] **Step 1: 既存テストのベースラインを確認**

```bash
uv run pytest tests/unit/test_app_menu.py -v
```

期待: 全テストがパス（これがリファクタリング後も維持されるべき状態）。

- [ ] **Step 2: `backend/app.py` を修正して `_activate_file` を追加**

`backend/app.py` の `_wait_for_server` 関数の直後（59行目付近）に追加し、`_open_file_from_menu` と `_build_open_recent_menu` 内の `_open_recent` を書き換える:

```python
def _activate_file(path: str, window: webview.Window) -> None:
    recent_files_service.add(path)
    watch_service.set_file(path)
    window.evaluate_js("window.location.reload()")


def _open_file_from_menu(window: webview.Window) -> None:
    result = window.create_file_dialog(
        FileDialog.OPEN,
        allow_multiple=False,
        file_types=("Mermaid files (*.mmd;*.mermaid)", "All files (*.*)"),
    )
    if result:
        _activate_file(result[0], window)


def _build_open_recent_menu(window: webview.Window) -> Menu:
    recent = recent_files_service.get()

    def _open_recent(path: str) -> None:
        _activate_file(path, window)

    if recent:
        items: list = [
            MenuAction(p, lambda p=p: _open_recent(p)) for p in recent
        ]
        items += [MenuSeparator(), MenuAction("Clear Menu", recent_files_service.clear)]
    else:
        items = [MenuAction("No Recent Files", lambda: None)]

    return Menu("Open Recent...", items)
```

- [ ] **Step 3: テストを実行してリグレッションがないことを確認**

```bash
uv run pytest tests/unit/test_app_menu.py -v
```

期待: 全テストがパス。

---

## Task 4: C4 — 起動時 `initial_file` を recent_files に追加

**Files:**
- Modify: `backend/app.py` (main 関数内)

> **テストについて:** `main()` は `webview.start()` を伴うため単体テストが困難。この 1 行追加はコードインスペクションで担保する。

- [ ] **Step 1: `backend/app.py` の `main()` を修正**

`main()` 内の `initial_file` 処理部分（120行目付近）を修正:

```python
    initial_file = (sys.argv[1] if len(sys.argv) > 1 else None) or state.get("last_file")
    if initial_file:
        recent_files_service.add(initial_file)   # ← この行を追加
        watch_service.set_file(initial_file)
```

- [ ] **Step 2: 全テストを実行してリグレッションがないことを確認**

```bash
uv run pytest -v --tb=short
```

期待: 全テストがパス。

- [ ] **Step 3: Task 2/3/4 をまとめてコミット**

```bash
git add backend/app.py backend/routers/html.py tests/integration/test_html_router.py
git commit -m "refactor: _activate_file ヘルパーでファイル開く処理を統一し recent_files の抜け漏れを修正する"
```

---

## Task 5: C6 — `_update_win` の競合状態をロックで修正

**Files:**
- Modify: `backend/update_window.py`
- Modify: `tests/unit/test_update_window.py`

- [ ] **Step 1: 失敗するテストを追加**

`tests/unit/test_update_window.py` の末尾に追加:

```python
import threading
import time


def test_open_update_dialog_concurrent_calls_create_one_window():
    """複数スレッドが同時に open_update_dialog() を呼んでも
    webview.create_window() は 1 回しか呼ばれない。"""
    import backend.update_window as uw

    uw._update_win = None  # 状態リセット
    create_calls = []

    def fake_create_window(**kwargs):
        time.sleep(0.05)  # race window を広げる
        win = MagicMock()
        win.events = MagicMock()
        create_calls.append(win)
        return win

    with patch("backend.update_window.webview.create_window", side_effect=fake_create_window):
        with patch("backend.update_window.update_service.invalidate_cache"):
            threads = [
                threading.Thread(target=uw.open_update_dialog, args=(8000,))
                for _ in range(3)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=2.0)

    assert len(create_calls) == 1, f"Expected 1 window, got {len(create_calls)}"

    uw._update_win = None  # クリーンアップ
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/unit/test_update_window.py::test_open_update_dialog_concurrent_calls_create_one_window -v
```

期待: `FAILED` — `AssertionError: Expected 1 window, got 3`（ロックなしなのでレースが発生）

> `got 1` になってしまう場合、OS スケジューリングの都合でレースが発生していない。その場合は `time.sleep(0.1)` に増やして再試行する。

- [ ] **Step 3: `backend/update_window.py` にロックを追加**

ファイル冒頭の `import threading` を確認し（既にある）、モジュールレベルに `_update_win_lock` を追加して `open_update_dialog` を書き換える:

```python
_update_win: webview.Window | None = None
_update_win_lock = threading.Lock()  # ← 追加
_menu_target: object | None = None


def open_update_dialog(port: int) -> None:
    """更新確認ダイアログを開く。すでに開いていれば何もしない。"""
    global _update_win
    with _update_win_lock:
        if _update_win is not None:
            return
        update_service.invalidate_cache()
        url = f"http://{HOST}:{port}/api/update/dialog"
        win = webview.create_window(
            title="アップデート確認",
            url=url,
            width=400,
            height=260,
            resizable=False,
        )
        if win is None:
            return

        def _on_closed() -> None:
            global _update_win
            with _update_win_lock:
                _update_win = None

        win.events.closed += _on_closed
        _update_win = win
```

- [ ] **Step 4: テストを実行してパスを確認**

```bash
uv run pytest tests/unit/test_update_window.py -v
```

期待: 全テストがパス。

- [ ] **Step 5: 全テストを実行してリグレッションがないことを確認**

```bash
uv run pytest -v --tb=short
```

期待: 全テストがパス。

- [ ] **Step 6: コミット**

```bash
git add backend/update_window.py tests/unit/test_update_window.py
git commit -m "fix: _update_win の check-then-assign を Lock で保護して競合状態を解消する"
```

---

## Task 6: C7 — `EventBus.notify()` のスナップショット反復

**Files:**
- Modify: `backend/services/event_bus.py`
- Modify: `tests/unit/test_event_bus.py`

- [ ] **Step 1: 失敗するテストを追加**

`tests/unit/test_event_bus.py` の末尾に追加:

```python
def test_notify_uses_snapshot_so_unsubscribe_during_iteration_is_safe():
    """notify() はリスナーリストのコピーを反復するため、
    反復中に unsubscribe() が呼ばれても RuntimeError が発生せず
    全リスナーに通知が届く。"""
    loop = asyncio.new_event_loop()
    b = EventBus()
    b.set_loop(loop)

    q1 = b.subscribe()
    q2 = b.subscribe()

    delivered: list[str] = []
    original_call_soon = loop.call_soon_threadsafe

    def call_soon_and_unsubscribe(fn, arg):
        if len(delivered) == 0:
            b.unsubscribe(q1)  # 1 回目の通知中にリスナーを削除
        delivered.append(arg)
        original_call_soon(fn, arg)

    loop.call_soon_threadsafe = call_soon_and_unsubscribe

    b.notify("reload")  # RuntimeError が出ないこと + 全リスナーに届くこと

    assert len(delivered) == 2, f"Expected 2 deliveries, got {len(delivered)}"
    loop.close()
```

- [ ] **Step 2: テストを実行して失敗を確認**

```bash
uv run pytest tests/unit/test_event_bus.py::test_notify_uses_snapshot_so_unsubscribe_during_iteration_is_safe -v
```

期待: `FAILED` — `AssertionError: Expected 2 deliveries, got 1`（`unsubscribe` で q1 が削除されると q2 がスキップされる）

> `got 2` になる場合、CPython の list iterator がその実行では要素をスキップしていない。
> `for q in self._listeners` を `for q in list(self._listeners)` に**まだ変えずに**、`time.sleep(0)` を `call_soon_and_unsubscribe` 内に追加してから再確認する。それでも `got 2` なら Step 3 に進み、修正後に `got 2` になることで正しさを確認する。

- [ ] **Step 3: `backend/services/event_bus.py` を修正**

```python
    def notify(self, event: str = "reload") -> None:
        if self._loop is None:
            return
        for q in list(self._listeners):        # ← list() でスナップショットを作成
            self._loop.call_soon_threadsafe(q.put_nowait, event)
```

- [ ] **Step 4: テストを実行してパスを確認**

```bash
uv run pytest tests/unit/test_event_bus.py -v
```

期待: 全テストがパス。

- [ ] **Step 5: 全テストを実行してリグレッションがないことを確認**

```bash
uv run pytest -v --tb=short
```

期待: 全テストがパス。

- [ ] **Step 6: コミット**

```bash
git add backend/services/event_bus.py tests/unit/test_event_bus.py
git commit -m "fix: EventBus.notify() をスナップショット反復に変えてスレッド安全性を確保する"
```

---

## 完了確認

全タスク完了後に実行:

```bash
uv run pytest -v --cov --cov-report=term-missing
```

期待:
- 全テストがパス
- カバレッジが 80% 以上（`fail_under = 80` の設定による）
