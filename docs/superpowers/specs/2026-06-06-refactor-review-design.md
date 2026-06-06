# リファクタリング設計書: コードレビュー改善

<!-- derived-from ./2026-06-05-refactor-improve-design.md -->

## 概要

コードレビューで指摘された6項目の改善を、機能別・インクリメンタルに実施する。
各改善は独立したコミットとして進め、リグレッションを最小化する。

## 改善項目と優先度

| 優先度 | 項目 | 対象ファイル |
|--------|------|-------------|
| 高 | CDN参照をローカルに修正 | `backend/templates/update_dialog.html` |
| 高 | `_Entry.path` の二重管理解消 | `backend/services/window_registry.py` |
| 中 | `app.py` を責務ごとに分割 | `backend/app.py` → 3ファイルに分割 |
| 中 | `update_service.py` をクラス化 | `backend/services/update_service.py` |
| 低 | `viewer.html` のインライン JS を外部化 | `backend/templates/viewer.html` |
| 低 | `do_install` フォールバック改善 | `backend/routers/update.py` |

---

## セクション 1: `app.py` の分割

### 現状

`backend/app.py` (307行) に以下の責務が混在している:

- サーバー起動 (`_find_free_port`, `_start_server`, `_wait_for_server`)
- ウィンドウライフサイクル (`_create_window`, `_open_file`, `_open_file_from_menu`, `_focus_window`)
- メニュー構築 (`_build_open_recent_menu`)
- 状態永続化 (`_load_window_states`, `_save_all_states`)
- Apple Events パッチ (`_patch_app_delegate_for_open_file`)
- アプリ起動ロジック (`main()`)

### 分割後の構成

```
backend/
  server.py          # サーバー起動ユーティリティ
  window_manager.py  # ウィンドウ生成・管理・メニュー
  state_store.py     # ウィンドウ状態の永続化
  app.py             # main() + Apple Events パッチのみ
```

#### `backend/server.py`

```python
def find_free_port() -> int: ...
def start_server(app, port: int) -> None: ...
def wait_for_server(port: int, timeout: float = 5.0) -> None: ...
```

#### `backend/window_manager.py`

```python
# モジュールレベル
_windows: dict[str, webview.Window] = {}

def focus_window(window: webview.Window) -> None: ...
def create_window(port, file_path=None, x=100, y=100, width=1024, height=768) -> tuple[str, webview.Window]: ...
def open_file(path: str, port: int) -> None: ...
def open_file_from_menu(port: int) -> None: ...
def build_open_recent_menu(port: int) -> Menu: ...
def get_windows() -> dict[str, webview.Window]: ...
```

#### `backend/state_store.py`

```python
def load_window_states() -> list[dict]: ...
def save_all_states() -> None: ...
```

#### `backend/app.py` (簡略化後)

- `_patch_app_delegate_for_open_file()` — Apple 固有の処理のため残留
- `main()` — 各モジュールを組み合わせるエントリポイント（50行程度）

### インターフェース

- `window_manager` は `window_registry` と `recent_files_service` に依存する
- `state_store` は `window_registry` と `window_manager._windows` に依存する
- `app.py` はすべてのモジュールを組み合わせる

---

## セクション 2: `update_service.py` のクラス化

### 現状

モジュールレベルのミュータブルグローバル変数で状態管理しており、テストが困難。

```python
_cache: dict = {"checked_at": None, "result": None}
_download_state: dict = {"percent": 0, "status": "idle", "dmg_path": None}
_state_lock = threading.Lock()
```

### 変更後

```python
class UpdateService:
    def __init__(self) -> None:
        self._cache: dict = {"checked_at": None, "result": None}
        self._download_state: dict = {"percent": 0, "status": "idle", "dmg_path": None}
        self._state_lock = threading.Lock()

    def check_update(self) -> dict: ...
    def get_download_state(self) -> dict: ...
    def download_update(self, url: str) -> None: ...
    def invalidate_cache(self) -> None: ...
    def _do_download(self, url: str, dest: Path | None = None) -> None: ...
    def _is_newer(self, remote: str, current: str) -> bool: ...
    def _find_dmg_url(self, assets: list[dict]) -> str | None: ...

# 後方互換シングルトン（呼び出し側の変更不要）
update_service = UpdateService()
```

モジュールレベルのプライベート関数 `_is_newer`, `_find_dmg_url`, `_do_download` はクラスのプライベートメソッドに移動する。

---

## セクション 3: CDN 参照の修正

### 現状

`update_dialog.html` だけが CDN 経由で htmx を読み込んでいる。コミット `b9cc171` でオフライン動作を実現したにもかかわらず、更新ダイアログが機能しない。

```html
<script src="https://unpkg.com/htmx.org@2.0.4" integrity="..." crossorigin="anonymous"></script>
```

### 変更後

```html
<script src="/static/js/htmx.min.js"></script>
```

---

## セクション 4: `_Entry.path` の二重管理解消

### 現状

`_Entry.path` と `WatchService._path` が同じ情報を保持している。`watch.set_file()` を後から呼んだ場合に `entry.path` が更新されず乖離するリスクがある。

### 変更後

`_Entry` から `path` フィールドを削除し、すべてのパス参照を `entry.watch.get_path()` 経由に統一する。

```python
@dataclass
class _Entry:
    watch: WatchService
    bus: EventBus
    # path フィールド削除

def find_by_path(self, path: str) -> str | None:
    p = Path(path)
    for wid, entry in self._entries.items():
        if entry.watch.get_path() == p:
            return wid
    return None

def snapshot(self) -> list[tuple[str, Path | None]]:
    return [(wid, entry.watch.get_path()) for wid, entry in self._entries.items()]
```

`create()` での `watch.set_file()` 呼び出しはそのまま維持する（`_Entry.path` への代入のみ削除）。

---

## セクション 5: インライン JS の外部化

### 現状

`viewer.html` の `<script>` タグ内にズーム機能（50行超）と EventSource 処理が直書きされている。

### 変更後

`/static/js/viewer.js` を新規作成し、すべての JS を移動する。

```html
<!-- viewer.html -->
<script src="/static/js/mermaid.min.js"></script>
<script src="/static/js/viewer.js"></script>
```

`viewer.js` の責務:
- mermaid の初期化設定
- ズーム機能（定数・状態・イベントハンドラ）
- EventSource によるリロード購読

---

## セクション 6: `do_install` フォールバック改善

### 現状

`not_frozen`（開発環境など凍結バイナリでない場合）に空レスポンスを返し、バナーが無言で消える。

```python
if result == "not_frozen":
    return HTMLResponse(content="")
```

### 変更後

`update_idle.html` パーシャルを返し、バナーを通常の「フォーカス時チェック」状態に戻す。ユーザーには何も起きなかったように見え、混乱を避けられる。

```python
if result == "not_frozen":
    return templates.TemplateResponse(request, "partials/update_idle.html", {})
```

---

## 実装順序

1. `update_dialog.html` CDN修正（最小変更・即効果）
2. `_Entry.path` 二重管理解消（データ整合性）
3. `update_service.py` クラス化（サービス層の整備）
4. `app.py` 分割（最大の構造変更、依存先が整った後）
5. `do_install` フォールバック改善（ルーター層）
6. `viewer.html` JS 外部化（テンプレート層）

## リスクと注意点

- `app.py` 分割は `window_manager` と `state_store` が `_windows` dict を共有するため、モジュール間の参照設計を慎重に行う（`window_manager` がオーナー、`state_store` は `window_manager.get_windows()` 経由でアクセス）
- `update_service` クラス化は公開インターフェースを変えないため、呼び出し側の変更は不要
- 各ステップ後に `python -c "from backend.app import main"` でインポートエラーがないことを確認する
