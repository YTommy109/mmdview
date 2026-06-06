# 複数ウィンドウ対応 設計書

Date: 2026-06-06

## 概要

現在シングルウィンドウのみ対応している mmdview を、複数の .mmd ファイルを同時に表示できる複数ウィンドウ対応に拡張する。

## 要件

### 新規ウィンドウを開くトリガー

以下のすべての操作で新しいウィンドウが開かれる:

- **File → Open...**: ダイアログでファイルを選択すると新ウィンドウで開く
- **Finder / ダブルクリック**: `.mmd` ファイルを Finder から開くと新ウィンドウで表示
- **Open Recent**: 最近使ったファイルの選択で新ウィンドウを開く
- **コマンドライン**: 既にアプリ起動中に `mmdview file.mmd` を実行すると新ウィンドウを開く

### 重複ファイルの処理

既に開いているファイルを再度開こうとした場合、新しいウィンドウを開かず既存ウィンドウをフォーカスする。

### ウィンドウ状態の復元

再起動時に前回開いていた全ウィンドウ（ファイル・位置・サイズ）を復元する。

## アーキテクチャ

### 方針: 共有サーバー + window_id パラメータ

1つの FastAPI サーバーを全ウィンドウで共有し、各ウィンドウを UUID (`window_id`) で識別する。

```
Window 1: http://127.0.0.1:{port}/?window_id=aaa  →  flowchart.mmd
Window 2: http://127.0.0.1:{port}/?window_id=bbb  →  sequence.mmd

FastAPI Server:
  WindowRegistry:
    aaa → WatchService(flowchart.mmd) + EventBus
    bbb → WatchService(sequence.mmd)  + EventBus
```

### 変更対象の一覧

| コンポーネント | 変更内容 |
|---|---|
| `backend/services/window_registry.py` | 新規追加 |
| `backend/services/watch_service.py` | グローバルシングルトン削除（Registry経由に） |
| `backend/services/event_bus.py` | グローバルシングルトン削除（Registry経由に） |
| `backend/routers/html.py` | `window_id` クエリパラメータ対応 |
| `backend/routers/events.py` | `window_id` クエリパラメータ対応 |
| `backend/app.py` | 複数ウィンドウ管理・open_file ロジック |
| `backend/paths.py` | window_state.json フォーマット変更 |

## 詳細設計

### WindowRegistry (`backend/services/window_registry.py`)

```python
class WindowRegistry:
    def create(self, window_id: str, file_path: str | None = None) -> None
    def get(self, window_id: str) -> tuple[WatchService, EventBus] | None
    def remove(self, window_id: str) -> None
    def find_by_path(self, path: str) -> str | None  # window_id or None
    def all_states(self) -> list[dict]  # 全ウィンドウの状態スナップショット

window_registry = WindowRegistry()
```

- `WatchService` と `EventBus` はグローバルシングルトンを廃止し、Registry 経由で取得する
- `remove()` は WatchService の `stop()` を呼んでから削除する

### ルーター変更

**`html.py`**:
```python
@router.get("/", response_class=HTMLResponse)
async def index(request: Request, window_id: str = "") -> HTMLResponse:
    entry = window_registry.get(window_id)
    ...
```

**`events.py`**:
```python
@router.get("/events")
async def sse_endpoint(request: Request, window_id: str = "") -> EventSourceResponse:
    entry = window_registry.get(window_id)
    _, event_bus = entry
    ...
```

### app.py のウィンドウ管理

**`open_file(path)` — 共通エントリーポイント:**
```
1. registry.find_by_path(path) で既存ウィンドウを探す
2. 見つかった → そのウィンドウをフォーカス
     pywebview に native focus API はないため、
     macOS では NSApp.activateIgnoringOtherApps + NSWindow.makeKeyAndOrderFront を
     evaluate_js 経由または AppKit 直接呼び出しで実現する
3. 見つからない → create_window(file_path=path) で新ウィンドウを開く
```

**`create_window(file_path=None)`:**
```
1. window_id = str(uuid4())
2. registry.create(window_id, file_path)
3. webview.create_window(url=f"http://.../?window_id={window_id}", ...)
4. window.events.closed += lambda: registry.remove(window_id) + save_state()
5. window.events.moved / resized += save_state()
```

### ウィンドウ状態ファイル

**変更前 (`window_state.json`):**
```json
{"x": 100, "y": 100, "width": 1024, "height": 768, "last_file": "/path/to/file.mmd"}
```

**変更後:**
```json
[
  {"x": 100, "y": 100, "width": 1024, "height": 768, "file": "/path/to/flowchart.mmd"},
  {"x": 500, "y": 200, "width": 800,  "height": 600, "file": "/path/to/sequence.mmd"}
]
```

**後方互換:** 旧フォーマット（辞書）を読み込んだ場合はリストに変換して処理する。

**保存タイミング:** ウィンドウの移動・リサイズ・クローズ時にデバウンス（0.5秒）して保存。

**復元ロジック:**
1. 起動時にリストを読み込む
2. コマンドライン引数でファイルが指定された場合はそちらのみを開く
3. 引数なしの場合は保存済みの全ウィンドウを復元する

## 非変更範囲

- `apple_events.py`: 既存の `register_open_file_handler` コールバックを `open_file()` に差し替えるだけ
- `update_window.py`: 更新ダイアログは独立したウィンドウのため変更不要
- フロントエンド HTML/CSS: `window_id` は URL パラメータで自動的に引き継がれるため変更不要
