# Hyperscript Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `static/js/viewer.js` を hyperscript に完全移行し、JS ファイルをゼロにする。

**Architecture:** `_hyperscript.min.js` と `htmx-ext-sse.js` を `download_js.py` でオフラインバンドルに追加する。ズームロジックを hyperscript の `behavior ZoomController` として `viewer.html` 内に定義し `#zoom-controls` にインストールする。SSE によるリロードは htmx-ext-sse と hyperscript の `on sse:message` で処理する。

**Tech Stack:** Python/FastAPI, Jinja2, htmx 2.0.4, hyperscript 0.9.14, htmx-ext-sse 2.2.2, pytest

---

## File Map

| ファイル | 変更内容 |
|---|---|
| `scripts/download_js.py` | `_hyperscript.min.js` と `htmx-ext-sse.js` の2エントリを追加 |
| `static/js/_hyperscript.min.js` | 新規（download_js.py で生成） |
| `static/js/htmx-ext-sse.js` | 新規（download_js.py で生成） |
| `backend/templates/base.html` | hyperscript `<script>` タグを追加 |
| `backend/routers/html.py` | `window_id` をテンプレートコンテキストに追加 |
| `backend/templates/viewer.html` | ZoomController behavior + SSE div に全面書き換え |
| `static/js/viewer.js` | **削除** |
| `tests/integration/test_html_router.py` | 3つのテストを追加 |

---

### Task 1: download_js.py にライブラリを追加してダウンロード

**Files:**
- Modify: `scripts/download_js.py`

- [ ] **Step 1: LIBS リストに2エントリを追加する**

`scripts/download_js.py` の `LIBS` リストを以下に更新する：

```python
LIBS = [
    {
        "name": "htmx.min.js",
        "url": "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js",
    },
    {
        "name": "mermaid.min.js",
        "url": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
    },
    {
        "name": "_hyperscript.min.js",
        "url": "https://unpkg.com/hyperscript.org@0.9.14/dist/_hyperscript.min.js",
    },
    {
        "name": "htmx-ext-sse.js",
        "url": "https://unpkg.com/htmx-ext-sse@2.2.2/sse.js",
    },
]
```

- [ ] **Step 2: ダウンロードを実行する**

```bash
uv run python scripts/download_js.py
```

期待出力：
```
Downloading htmx.min.js ... done (xxx.x KB)
Downloading mermaid.min.js ... done (xxx.x KB)
Downloading _hyperscript.min.js ... done (xxx.x KB)
Downloading htmx-ext-sse.js ... done (xx.x KB)
All libraries saved to .../static/js
```

- [ ] **Step 3: ファイルが存在することを確認する**

```bash
ls static/js/
```

期待出力に `_hyperscript.min.js` と `htmx-ext-sse.js` が含まれること。

- [ ] **Step 4: コミットする**

```bash
git add scripts/download_js.py static/js/_hyperscript.min.js static/js/htmx-ext-sse.js
git commit -m "feat: _hyperscript.min.js と htmx-ext-sse.js をオフラインバンドルに追加する"
```

---

### Task 2: base.html に hyperscript を追加する

**Files:**
- Modify: `backend/templates/base.html`
- Test: `tests/integration/test_html_router.py`

- [ ] **Step 1: 失敗するテストを追加する**

`tests/integration/test_html_router.py` の末尾に追記する：

```python
def test_viewer_includes_hyperscript(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-hyper-check", str(f))

    response = client.get("/?window_id=w-hyper-check")
    assert response.status_code == 200
    assert "_hyperscript.min.js" in response.text
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/integration/test_html_router.py::test_viewer_includes_hyperscript -v
```

期待出力: `FAILED` (`AssertionError`)

- [ ] **Step 3: base.html を編集する**

`backend/templates/base.html` の htmx script タグの直後に1行追加する：

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>mmdview</title>
  <script src="/static/js/htmx.min.js"></script>
  <script src="/static/js/_hyperscript.min.js"></script>
  <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
  <div id="update-banner"
       hx-get="/api/update/check"
       hx-trigger="load, focus from:window"
       hx-swap="outerHTML">
  </div>
  {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: テストが通ることを確認する**

```bash
uv run pytest tests/integration/test_html_router.py::test_viewer_includes_hyperscript -v
```

期待出力: `PASSED`

- [ ] **Step 5: 既存テストが壊れていないことを確認する**

```bash
uv run pytest tests/integration/test_html_router.py -v
```

期待出力: 全テスト `PASSED`

- [ ] **Step 6: コミットする**

```bash
git add backend/templates/base.html tests/integration/test_html_router.py
git commit -m "feat: base.html に hyperscript を追加する"
```

---

### Task 3: viewer.html を書き換えて html.py で window_id を渡す

**Files:**
- Modify: `backend/routers/html.py`
- Modify: `backend/templates/viewer.html`
- Test: `tests/integration/test_html_router.py`

- [ ] **Step 1: 失敗するテストを2つ追加する**

`tests/integration/test_html_router.py` の末尾に追記する：

```python
def test_viewer_has_sse_connect_with_window_id(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-sse-check", str(f))

    response = client.get("/?window_id=w-sse-check")
    assert response.status_code == 200
    assert 'sse-connect="/events?window_id=w-sse-check"' in response.text


def test_viewer_has_zoom_controller_and_no_viewer_js(client, tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    from backend.services.window_registry import window_registry

    window_registry.create("w-zc-check", str(f))

    response = client.get("/?window_id=w-zc-check")
    assert response.status_code == 200
    assert "install ZoomController" in response.text
    assert "viewer.js" not in response.text
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/integration/test_html_router.py::test_viewer_has_sse_connect_with_window_id tests/integration/test_html_router.py::test_viewer_has_zoom_controller_and_no_viewer_js -v
```

期待出力: どちらも `FAILED`

- [ ] **Step 3: html.py を編集して window_id をテンプレートに渡す**

`backend/routers/html.py` の `viewer.html` への `TemplateResponse` 呼び出しを修正する：

```python
return templates.TemplateResponse(
    request,
    "viewer.html",
    {"content": content, "window_id": window_id},
)
```

ファイル全体は以下の通り：

```python
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
        {"content": content, "window_id": window_id},
    )
```

- [ ] **Step 4: viewer.html を全面書き換えする**

`backend/templates/viewer.html` を以下の内容で置き換える：

```html
{% extends "base.html" %}
{% block content %}

<script type="text/hyperscript">
behavior ZoomController
  init
    set :zoom to js return parseFloat(localStorage.getItem('mmdview.viewer.zoom') || '1') || 1 end
    call applyZoom()
  end

  def applyZoom()
    if :zoom < 0.5 set :zoom to 0.5 end
    if :zoom > 2.0 set :zoom to 2.0 end
    set the style.zoom of #diagram-wrap to :zoom
    set the textContent of #zoom-label to (Math.round(:zoom * 100) + '%')
    set #zoom-in.disabled to (:zoom >= 2.0)
    set #zoom-out.disabled to (:zoom <= 0.5)
    call localStorage.setItem('mmdview.viewer.zoom', :zoom)
  end

  on click from #zoom-in
    set :zoom to Math.round((:zoom + 0.25) * 100) / 100
    call applyZoom()
  end

  on click from #zoom-out
    set :zoom to Math.round((:zoom - 0.25) * 100) / 100
    call applyZoom()
  end

  on click from #zoom-label
    set :zoom to 1
    call applyZoom()
  end

  on keydown[metaKey and (key is '=' or key is '+' or key is '-')] from document
    halt the event
    if key is '-'
      set :zoom to Math.round((:zoom - 0.25) * 100) / 100
    else
      set :zoom to Math.round((:zoom + 0.25) * 100) / 100
    end
    call applyZoom()
  end

  on wheel[ctrlKey] from document
    halt the event
    set :zoom to Math.round((:zoom - event.deltaY * 0.01) * 1000) / 1000
    call applyZoom()
  end
end
</script>

<div class="viewer">
  <div id="diagram-wrap">
    <pre class="mermaid">{{ content }}</pre>
  </div>
</div>

<div class="zoom-controls" _="install ZoomController">
  <button id="zoom-out" title="縮小 (Cmd −)">−</button>
  <span id="zoom-label" title="クリックでリセット">100%</span>
  <button id="zoom-in" title="拡大 (Cmd +)">+</button>
</div>

<div hx-ext="sse"
     sse-connect="/events?window_id={{ window_id }}"
     _="on sse:message
          if event.detail.data is 'reload'
            call location.reload()">
</div>

<script src="/static/js/mermaid.min.js"></script>
<script src="/static/js/htmx-ext-sse.js"></script>
<script>
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
</script>
{% endblock %}
```

- [ ] **Step 5: 2つのテストが通ることを確認する**

```bash
uv run pytest tests/integration/test_html_router.py::test_viewer_has_sse_connect_with_window_id tests/integration/test_html_router.py::test_viewer_has_zoom_controller_and_no_viewer_js -v
```

期待出力: どちらも `PASSED`

- [ ] **Step 6: 統合テスト全件が通ることを確認する**

```bash
uv run pytest tests/integration/ -v
```

期待出力: 全テスト `PASSED`

- [ ] **Step 7: コミットする**

```bash
git add backend/routers/html.py backend/templates/viewer.html tests/integration/test_html_router.py
git commit -m "feat: viewer.html を hyperscript ZoomController behavior と SSE に書き換える"
```

---

### Task 4: viewer.js を削除して全テストを確認する

**Files:**
- Delete: `static/js/viewer.js`

- [ ] **Step 1: viewer.js を削除する**

```bash
git rm static/js/viewer.js
```

- [ ] **Step 2: 全テストが通ることを確認する**

```bash
uv run pytest -v
```

期待出力: 全テスト `PASSED`

- [ ] **Step 3: コミットする**

```bash
git commit -m "chore: viewer.js を削除する（hyperscript に完全移行）"
```

---

## 手動スモークテスト（実装完了後）

以下を実際のアプリで確認すること（自動テストでは担保できないブラウザ動作）：

- [ ] ズームインボタン（＋）でダイアグラムが拡大される
- [ ] ズームアウトボタン（−）でダイアグラムが縮小される
- [ ] ズームラベルをクリックすると 100% にリセットされる
- [ ] Cmd+= / Cmd++ でズームイン、Cmd+- でズームアウトされる
- [ ] Ctrl+ホイールでズームが変化する
- [ ] ズーム上限 200%・下限 50% でボタンが無効化される
- [ ] ページリロード後に前回のズーム値が復元される
- [ ] .mmd ファイルを更新するとページが自動リロードされる
