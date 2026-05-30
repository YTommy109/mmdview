# mmdview — 設計ドキュメント

**日付**: 2026-05-30
**ステータス**: 承認済み

## 概要

mmdview は `.mmd` / `.md` ファイルを監視してリアルタイムで Mermaid 図をプレビューする macOS デスクトップアプリ。git-lanes と同一アーキテクチャ（Python + FastAPI + pywebview + htmx + watchdog）を採用する。

---

## アーキテクチャ

```
mmdview.app (PyInstaller バンドル)
  ├── FastAPI サーバー（別スレッド、ランダムポート）
  └── WKWebView ウィンドウ（pywebview）
       └── http://127.0.0.1:{PORT}/ を表示
```

通信はすべてローカルホスト HTTP。ネイティブブリッジは使用しない。

---

## プロジェクト構造

```
mmdview/
├── backend/
│   ├── app.py              # pywebview エントリポイント・ウィンドウ管理
│   ├── main.py             # FastAPI アプリ定義
│   ├── paths.py            # アプリデータディレクトリ定義
│   ├── routers/
│   │   ├── html.py         # GET / (welcome / viewer HTML)
│   │   └── events.py       # GET /events (SSE ストリーム)
│   ├── services/
│   │   ├── watch_service.py  # watchdog でファイル監視・ファイル内容取得
│   │   └── event_bus.py      # watchdog スレッド → asyncio ブリッジ
│   └── templates/
│       ├── base.html         # レイアウト共通テンプレート
│       ├── welcome.html      # ファイル未選択時の初期画面
│       └── viewer.html       # mermaid.js を使った表示画面
├── static/
│   └── css/style.css
├── docs/
│   └── superpowers/specs/
│       └── 2026-05-30-mmdview-design.md
├── pyproject.toml
├── uv.lock
└── mmdview.spec              # PyInstaller 設定
```

---

## データフロー

### 起動

1. `app.py` が FastAPI をバックグラウンドスレッドで起動（ランダムポートを取得）
2. `~/Library/Application Support/mmdview/window_state.json` からウィンドウ状態を復元
3. 前回開いたファイルパスが保存されていれば自動で監視を再開
4. pywebview が WKWebView ウィンドウを開く

### ファイル選択

1. ユーザーが「ファイルを開く」ボタンをクリック（または `⌘O`）
2. htmx が `POST /open-file` を送信
3. FastAPI が `pywebview.windows[0].create_file_dialog()` を呼ぶ（OS 標準ダイアログ）
4. ユーザーが `.mmd` または `.md` ファイルを選択
5. `watch_service.set_file(path)` を呼び watchdog 監視を開始
6. FastAPI がファイル内容を読み込み viewer.html を返す（htmx swap）

### 表示

1. `viewer.html` の `<pre class="mermaid">` タグにファイルテキストを埋め込む
   - `.mmd` ファイル: ファイル全体をそのまま埋め込む
   - `.md` ファイル: ファイル全体をそのまま埋め込む（mermaid.js が ` ```mermaid ` フェンスを自動処理する）
2. mermaid.js（CDN）が DOM をスキャンして SVG をレンダリング
3. JavaScript が `GET /events` に SSE 接続を確立

### ファイル変更検知・自動リロード

1. watchdog が対象ファイルの変更を検知
2. `event_bus.notify()` でイベントを発行（watchdog スレッド → asyncio ブリッジ）
3. SSE ストリームへ `data: reload` イベントを送信
4. フロントエンド JS が `window.location.reload()` を呼ぶ
5. FastAPI が最新のファイル内容を返し mermaid.js が再レンダリング

---

## UI / UX

### 初期画面（welcome.html）

- 中央に「ファイルを開く」ボタンのみ表示
- `.mmd` / `.md` ファイルを選択するよう促すメッセージ

### ビューア画面（viewer.html）

- **ツールバー（上部）**:
  - 現在開いているファイル名（フルパス）表示
  - 「別のファイルを開く」ボタン
- **メインエリア**: mermaid.js がレンダリングした SVG（スクロール可能）
- ファイル変更時は自動リロード（画面の一瞬のちらつきは許容）

### macOS メニューバー

- `File > Open...`（`⌘O`）: ファイルダイアログを開く
- `File > Close`（`⌘W`）: ウィンドウを閉じる

### エラー処理

- Mermaid 構文エラーは mermaid.js がSVG内にエラーメッセージを表示するため Python 側での処理は不要
- ファイルが読み込めない場合（削除・権限エラー）は welcome.html へフォールバック

---

## 技術スタック

| パッケージ | 用途 |
|---|---|
| fastapi | REST / HTML サーバー |
| uvicorn[standard] | ASGI サーバー |
| pywebview | macOS WKWebView ラッパー |
| watchdog | ファイルシステム監視 |
| sse-starlette | Server-Sent Events |
| jinja2 | HTML テンプレート |
| mermaid.js | Mermaid SVG レンダリング（CDN） |

**開発ツール**:
- `uv`: パッケージ管理
- `taskipy`: タスクランナー（`uv run task dev` / `uv run task build`）
- `ruff`: リント・フォーマット
- `pyinstaller`: `.app` バンドル生成

**mermaid.js**: 初期スコープでは CDN（`cdn.jsdelivr.net`）からロード。

---

## 永続化

`~/Library/Application Support/mmdview/window_state.json`:

```json
{
  "x": 100,
  "y": 100,
  "width": 1024,
  "height": 768,
  "last_file": "/path/to/diagram.mmd"
}
```

ウィンドウ移動・リサイズ時にデバウンス（500ms）で保存。アプリ再起動時に復元し、`last_file` があれば自動で監視を再開する。

---

## スコープ外

- エクスポート機能（SVG / PNG）
- ドラッグ＆ドロップによるファイル指定
- 複数ファイルの同時表示
- オフライン用 mermaid.js バンドル（初期スコープ）
