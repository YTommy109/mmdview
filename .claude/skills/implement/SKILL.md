# mmdview 実装スキル

mmdview に新機能を追加または既存コードを変更するときの制約。

## ファイルパス

PyInstaller バンドル互換のため、ファイルパスは必ず `backend/paths.py` の定数を使う:

```python
from backend.paths import BASE_DIR, TEMPLATES_DIR, STATIC_DIR
```

`os.getcwd()` や相対パス文字列（`"static"`, `"backend/templates"`）を直接渡さない。

## pywebview の分離

`import webview` はテストが走る場所では行わない。ルーターでファイルダイアログを呼ぶ場合は
関数内でのみインポートする:

```python
def _pick_file() -> str | None:
    import webview  # ここでのみインポート
    result = webview.windows[0].create_file_dialog(...)
    return result[0] if result else None
```

## SSE テスト

`TestClient` は SSE 無限ストリームをハングさせるため、SSE エンドポイントのテストは
ルート登録確認のみ行う:

```python
def test_events_route_is_registered():
    from backend.main import app
    from fastapi.routing import APIRoute
    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    assert "/events" in paths
```

## EventBus の使い方

watchdog スレッドから asyncio へのイベント送信は `event_bus.notify()` を呼ぶ。
`asyncio.run()` や新規ループ作成はしない。

## テンプレートレスポンス

Starlette 1.x 以降の API を使う:

```python
# 正しい
templates.TemplateResponse(request, "template.html", {"key": "value"})

# 古い書き方（非推奨）
templates.TemplateResponse("template.html", {"request": request, "key": "value"})
```

## WatchService のテスト

`WatchService` はテスト用に `event_bus` を注入できる:

```python
svc = WatchService(event_bus=mock_bus)
```

本番コードはモジュールレベルのシングルトン `watch_service` を使う。
