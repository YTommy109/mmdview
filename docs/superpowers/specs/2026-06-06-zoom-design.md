# ズーム機能 設計書

Date: 2026-06-06

## 概要

mmdview のビューワー画面に図の拡大縮小機能を追加する。ピンチジェスチャー、キーボードショートカット、右上フローティングパネルの +/− ボタンの 3 つの操作方法を提供する。倍率はアプリ終了をまたいで保持する。

## 要件

| 項目 | 仕様 |
|------|------|
| ズーム範囲 | 50% 〜 200% |
| ボタンステップ | 25% 刻み |
| ピンチ操作 | 連続ズーム（滑らか） |
| キーボード | Cmd + / Cmd − |
| % 表示クリック | 100% にリセット |
| 倍率の永続化 | localStorage に保存・ページロード時に復元 |

## 変更ファイル

変更するのは 2 ファイルのみ。バックエンドの変更は不要。

| ファイル | 変更内容 |
|----------|----------|
| `backend/templates/viewer.html` | ズームコントロール UI + JS ロジック |
| `static/css/style.css` | ズームコントロールパネルのスタイル |

## UI 設計

### ズームコントロールパネル

ビューワー右上に `position: fixed` で配置するフローティングパネル。

```
[ − ]  100%  [ + ]
```

- `−` ボタン: 25% 減算（50% 下限）
- `+` ボタン: 25% 加算（200% 上限）
- `100%` 表示: クリックで 100% にリセット。ホバー時に青色でリセット可能であることを示す

### スタイル方針

- 背景: `rgba(255,255,255,0.92)` + `backdrop-filter: blur(8px)` でガラス調
- 枠線: `1px solid rgba(0,0,0,0.12)` で控えめに
- 影: `box-shadow: 0 1px 4px rgba(0,0,0,0.1)`
- 角丸: `border-radius: 8px`
- z-index: 1000（図の上に常に表示）

## HTML 構造

`viewer.html` の変更点:

```html
<!-- 変更前 -->
<div class="viewer">
  <pre class="mermaid">{{ content }}</pre>
</div>

<!-- 変更後 -->
<div class="viewer">
  <div id="diagram-wrap">
    <pre class="mermaid">{{ content }}</pre>
  </div>
</div>

<div class="zoom-controls">
  <button id="zoom-out">−</button>
  <span id="zoom-label" title="クリックでリセット">100%</span>
  <button id="zoom-in">+</button>
</div>
```

`#diagram-wrap` が CSS `zoom` プロパティの適用対象。`.viewer` は変更しない。

## ズームロジック（JavaScript）

```js
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 2.0;
const ZOOM_STEP = 0.25;

let zoom = parseFloat(localStorage.getItem('zoom') || '1');

function applyZoom() {
  document.getElementById('diagram-wrap').style.zoom = zoom;
  document.getElementById('zoom-label').textContent =
    Math.round(zoom * 100) + '%';
  localStorage.setItem('zoom', zoom);
}

// ボタン操作
document.getElementById('zoom-in').addEventListener('click', () => {
  zoom = Math.min(ZOOM_MAX, zoom + ZOOM_STEP);
  applyZoom();
});
document.getElementById('zoom-out').addEventListener('click', () => {
  zoom = Math.max(ZOOM_MIN, zoom - ZOOM_STEP);
  applyZoom();
});

// % クリックでリセット
document.getElementById('zoom-label').addEventListener('click', () => {
  zoom = 1;
  applyZoom();
});

// ピンチジェスチャー（macOS トラックパッド → ctrlKey=true の wheel イベント）
document.addEventListener('wheel', (e) => {
  if (!e.ctrlKey) return;
  e.preventDefault();
  zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom - e.deltaY * 0.01));
  applyZoom();
}, { passive: false });

// キーボードショートカット
document.addEventListener('keydown', (e) => {
  if (!e.metaKey) return;
  if (e.key === '=' || e.key === '+') {
    e.preventDefault();
    zoom = Math.min(ZOOM_MAX, zoom + ZOOM_STEP);
    applyZoom();
  } else if (e.key === '-') {
    e.preventDefault();
    zoom = Math.max(ZOOM_MIN, zoom - ZOOM_STEP);
    applyZoom();
  }
});

// 初期適用（localStorage から復元）
applyZoom();
```

## 実装メモ

- CSS `zoom` を選んだ理由: pywebview は WebKit ベースで `zoom` プロパティを完全サポート。`transform: scale()` と違いレイアウト上のサイズも変わるため、`.viewer` のスクロール領域が自然に追従する
- ピンチジェスチャーは macOS トラックパッドが `ctrlKey: true` 付きの `wheel` イベントを発行する仕様を利用する
- `zoom` の適用先を `.viewer` でなく `#diagram-wrap` にすることで、ズームがビューワー全体の flex レイアウトに干渉しない

## 非変更範囲

- バックエンド（Python）: 変更なし
- `welcome.html` / `base.html`: 変更なし
- 他の HTML テンプレート: 変更なし
