# Design: viewer.js を hyperscript に移行する

## 概要

`static/js/viewer.js` をすべて hyperscript に置き換え、JS ファイルを削除する。
オフライン動作を維持するため、`_hyperscript.min.js` と `htmx-ext-sse.js` を
`download_js.py` 経由でバンドルする。

## 変更ファイル

| ファイル | 変更種別 |
|---|---|
| `scripts/download_js.py` | 編集 — 2ライブラリ追加 |
| `backend/templates/base.html` | 編集 — hyperscript script タグ追加 |
| `backend/templates/viewer.html` | 編集 — ZoomController behavior + SSE接続 |
| `backend/routers/html.py` | 編集 — window_id をテンプレートコンテキストへ追加 |
| `static/js/viewer.js` | **削除** |

## ライブラリ追加 (`download_js.py`)

```python
{
    "name": "_hyperscript.min.js",
    "url": "https://unpkg.com/hyperscript.org@0.9.14/dist/_hyperscript.min.js",
},
{
    "name": "htmx-ext-sse.js",
    "url": "https://unpkg.com/htmx-ext-sse@2.2.2/sse.js",
},
```

## `base.html` の変更

htmx の `<script>` タグの直後に追加する：

```html
<script src="/static/js/_hyperscript.min.js"></script>
```

hyperscript は全ページで使えるようにするため `base.html` に置く。
`htmx-ext-sse.js` は viewer のみで必要なため `viewer.html` に置く。

## `html.py` の変更

`viewer.html` テンプレートに `window_id` を渡す。
現状は `content` のみ渡しているため、SSE接続URLをサーバー側で組み立てられない。

```python
return templates.TemplateResponse(
    request,
    "viewer.html",
    {"content": content, "window_id": window_id},
)
```

## `viewer.html` の設計

### スクリプト読み込み順序

```html
<!-- base.html から継承 -->
<!-- htmx.min.js, _hyperscript.min.js, style.css -->

<!-- viewer.html 内 -->
<script src="/static/js/mermaid.min.js"></script>
<script src="/static/js/htmx-ext-sse.js"></script>
<script>mermaid.initialize({
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
});</script>
```

mermaid.initialize() は mermaid.min.js の読み込み後に実行する必要があるため、
同ファイルの後に inline script として置く。

### ZoomController behavior

`<script type="text/hyperscript">` ブロックで定義し、
`#zoom-controls` に `install ZoomController` でインストールする。

```
behavior ZoomController
  init
    set :zoom to parseFloat(localStorage.getItem('mmdview.viewer.zoom') or '1')
    if :zoom is NaN or :zoom is not a Number set :zoom to 1 end
    call applyZoom()
  end

  def applyZoom()
    -- Math.max/min のクランプ
    if :zoom < 0.5 set :zoom to 0.5 end
    if :zoom > 2.0 set :zoom to 2.0 end
    -- DOM 更新
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
```

**状態管理**: `:zoom` 変数は element-scoped（`#zoom-controls` 要素にバインド）。
behavior 内の全ハンドラが同じスコープを共有する。

**数値計算**: `Math.round`、`Math.max`、`Math.min` は hyperscript から
直接呼び出せる。

### SSE接続

```html
<div hx-ext="sse"
     sse-connect="/events?window_id={{ window_id }}"
     _="on sse:message
          if event.detail.data is 'reload'
            call location.reload()">
</div>
```

htmx-ext-sse は SSE メッセージ受信時に `sse:<event-type>` のカスタムイベントを発火する。
名前なしメッセージ（event type: `message`）は `sse:message` として扱われる。
現在のサーバー側は `{"data": event}` 形式で送信しているため変更不要。

## 削除

`static/js/viewer.js` を削除する。
このファイルの全機能を hyperscript に移行する。

## テスト観点

- ズームイン/アウトボタンが正しく動作すること
- Cmd+/- キーボードショートカットが動作すること
- Ctrl+ホイールでズームが変化すること
- ズームラベルクリックでリセットされること
- ズーム値が localStorage に保存・復元されること
- ズームの上限(200%)/下限(50%)が正しく機能すること
- ファイル変更時に自動リロードされること
