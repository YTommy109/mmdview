# 上部帯削除・ウィンドウタイトルへのファイル名表示 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** viewer 上部の toolbar（ファイル名 + 「別のファイルを開く」ボタン）を削除し、描画エリアをウィンドウ全体に広げる。ファイル名は pywebview の `window.title` を通じて macOS タイトルバーに表示する。

**Architecture:** html.py から `/open-file` エンドポイントと `_pick_file` を削除し、viewer.html の toolbar div を除去する。`backend/app.py` の `_activate_file` と `_on_open_file` で `window.title = Path(path).name` をセットする。起動時に initial_file がある場合は `webview.create_window` の `title` 引数で直接指定する。

**Tech Stack:** Python 3.13, pywebview, FastAPI, Jinja2, htmx, pytest + FastAPI TestClient

---

### Task 1: html ルーターテストを新しい仕様に合わせて更新する

**Files:**
- Modify: `tests/integration/test_html_router.py`

- [ ] **Step 1: /open-file 系テスト 4 本を削除する**

`tests/integration/test_html_router.py` から以下の関数を丸ごと削除する：

```python
# 削除する関数:
# test_open_file_sets_file_and_redirects
# test_open_file_does_nothing_when_cancelled
# test_open_file_adds_to_recent_files
# test_pick_file_uses_mermaid_extension
```

- [ ] **Step 2: viewer テストの `assert "test.mmd" in response.text` を書き換える**

`test_index_shows_viewer_when_file_set` の中で `assert "test.mmd" in response.text` を削除し、代わりに toolbar が存在しないことと、mermaid コンテンツが存在することを確認するアサーションに置き換える：

```python
def test_index_shows_viewer_when_file_set(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.watch_service import watch_service

    watch_service.set_file(str(f))

    response = client.get("/")
    assert response.status_code == 200
    assert "graph TD" in response.text
    assert 'class="toolbar"' not in response.text
```

- [ ] **Step 3: テストを実行して失敗を確認する**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待される結果: `test_index_shows_viewer_when_file_set` が FAIL（toolbar がまだ存在するため `assert 'class="toolbar"' not in response.text` が失敗する）

- [ ] **Step 4: コミットする**

```bash
git add tests/integration/test_html_router.py
git commit -m "test: toolbar 削除・/open-file 廃止に合わせてテストを更新する"
```

---

### Task 2: html.py から /open-file エンドポイントと不要な template 変数を削除する

**Files:**
- Modify: `backend/routers/html.py`

- [ ] **Step 1: `_pick_file` 関数と `POST /open-file` ハンドラを削除する**

`backend/routers/html.py` を以下の内容に置き換える：

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.paths import TEMPLATES_DIR
from backend.services.watch_service import watch_service

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    content = watch_service.get_content()
    path = watch_service.get_path()
    if content is None or path is None:
        return templates.TemplateResponse(request, "welcome.html")
    return templates.TemplateResponse(
        request,
        "viewer.html",
        {"content": content},
    )
```

削除されるもの:
- `_pick_file()` 関数
- `POST /open-file` ハンドラ (`async def open_file`)
- `recent_files_service` のインポート
- `Response` のインポート
- template context の `filename` と `filepath`

- [ ] **Step 2: テストを実行して成功を確認する**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待される結果: `test_index_shows_viewer_when_file_set` が PASS。全テストが PASS。

- [ ] **Step 3: コミットする**

```bash
git add backend/routers/html.py
git commit -m "feat: /open-file エンドポイントと不要なテンプレート変数を削除する"
```

---

### Task 3: viewer.html から toolbar を削除する

**Files:**
- Modify: `backend/templates/viewer.html`

- [ ] **Step 1: toolbar div を削除する**

`backend/templates/viewer.html` を以下の内容に置き換える：

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

  const evtSource = new EventSource('/events');
  evtSource.onmessage = (e) => {
    if (e.data === 'reload') window.location.reload();
  };
</script>
{% endblock %}
```

- [ ] **Step 2: テストを実行して成功を確認する**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待される結果: 全テストが PASS。

- [ ] **Step 3: コミットする**

```bash
git add backend/templates/viewer.html
git commit -m "feat: viewer から toolbar を削除して描画エリアをウィンドウ全体に広げる"
```

---

### Task 4: CSS から toolbar 関連スタイルを削除する

**Files:**
- Modify: `static/css/style.css`

- [ ] **Step 1: 不要スタイルを削除する**

`static/css/style.css` から以下のルールを削除する（`.toolbar`、`.filepath`、`button`、`button:hover`）。

削除後のファイル全体：

```css
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 16px;
}

.welcome-message {
  font-size: 14px;
  color: #666;
}

.viewer {
  flex: 1;
  overflow: auto;
  padding: 32px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}
```

- [ ] **Step 2: テストを実行して成功を確認する**

```bash
uv run pytest tests/ -v
```

期待される結果: 全テストが PASS。

- [ ] **Step 3: コミットする**

```bash
git add static/css/style.css
git commit -m "style: toolbar 関連の CSS を削除する"
```

---

### Task 5: `_activate_file` でウィンドウタイトルを更新するテストと実装を追加する

**Files:**
- Modify: `tests/unit/test_app_menu.py`
- Modify: `backend/app.py`

- [ ] **Step 1: `_activate_file` の window.title テストを追加する**

`tests/unit/test_app_menu.py` の import 行を更新して `_activate_file` を追加する：

```python
from backend.app import _activate_file, _build_open_recent_menu, _open_file_from_menu
```

次に、ファイル末尾に以下のテストを追加する：

```python
# ---------------------------------------------------------------------------
# _activate_file
# ---------------------------------------------------------------------------


@patch("backend.app.watch_service")
@patch("backend.app.recent_files_service")
def test_activate_file_sets_window_title(mock_recent_svc, mock_watch_svc):
    window = MagicMock()
    _activate_file("/some/dir/diagram.mmd", window)
    assert window.title == "diagram.mmd"


@patch("backend.app.watch_service")
@patch("backend.app.recent_files_service")
def test_activate_file_sets_title_to_filename_only(mock_recent_svc, mock_watch_svc):
    window = MagicMock()
    _activate_file("/Users/alice/projects/sequence.mmd", window)
    assert window.title == "sequence.mmd"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```bash
uv run pytest tests/unit/test_app_menu.py::test_activate_file_sets_window_title tests/unit/test_app_menu.py::test_activate_file_sets_title_to_filename_only -v
```

期待される結果: 両テストが FAIL（`_activate_file` がまだ `window.title` を設定しないため）

- [ ] **Step 3: `backend/app.py` に `from pathlib import Path` を追加して `_activate_file` を更新する**

`backend/app.py` の既存 import ブロックに `from pathlib import Path` を追加する（`import sys` の直後）：

```python
import json
import socket
import sys
from pathlib import Path
import threading
import time
from collections.abc import Callable
```

次に `_activate_file` 関数を以下のように更新する：

```python
def _activate_file(path: str, window: webview.Window) -> None:
    recent_files_service.add(path)
    watch_service.set_file(path)
    window.title = Path(path).name
    window.evaluate_js("window.location.reload()")
```

- [ ] **Step 4: テストを実行して成功を確認する**

```bash
uv run pytest tests/unit/test_app_menu.py -v
```

期待される結果: 全テストが PASS。

- [ ] **Step 5: `_on_open_file` 内の `_reload` でも window.title を更新する**

`backend/app.py` の `_on_open_file` 関数内の `_reload` を以下のように更新する：

```python
def _on_open_file(path: str) -> None:
    logger.info("_on_open_file called: path=%s", path)
    try:
        recent_files_service.add(path)
        watch_service.set_file(path)
    except Exception:
        import traceback

        logger.error("watch_service.set_file failed: path=%s\n%s", path, traceback.format_exc())
        return

    def _reload() -> None:
        try:
            for win in webview.windows:
                win.title = Path(path).name
                win.evaluate_js("window.location.reload()")
        except Exception:
            import traceback

            logger.error("_reload failed:\n%s", traceback.format_exc())

    threading.Thread(target=_reload, daemon=True).start()
```

- [ ] **Step 6: 起動時の initial_file がある場合のタイトルを `create_window` で設定する**

`backend/app.py` の `webview.create_window(...)` 呼び出しを以下のように変更する：

```python
window = webview.create_window(
    Path(initial_file).name if initial_file else "mmdview",
    f"http://127.0.0.1:{port}/",
    x=state.get("x", 100),
    y=state.get("y", 100),
    width=state.get("width", 1024),
    height=state.get("height", 768),
)
```

- [ ] **Step 7: 全テストを実行して成功を確認する**

```bash
uv run pytest tests/ -v
```

期待される結果: 全テストが PASS。

- [ ] **Step 8: コミットする**

```bash
git add backend/app.py tests/unit/test_app_menu.py
git commit -m "feat: ファイルを開いたときにウィンドウタイトルをファイル名に更新する"
```
