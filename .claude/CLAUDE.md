# mmdview

macOS 向け Mermaid ダイアグラム・ビューアアプリ。
`.mmd` / `.md` ファイルを監視し、mermaid.js でリアルタイムにプレビューする。

## アーキテクチャ

```
mmdview.app (PyInstaller バンドル)
  ├── FastAPI サーバー（別スレッド、ランダムポート）
  └── WKWebView ウィンドウ（pywebview）
       └── http://127.0.0.1:{PORT}/ を表示
```

通信はすべてローカルホスト HTTP。watchdog が変更を検知し SSE 経由でブラウザに通知、
mermaid.js が SVG をレンダリングする。

## 技術スタック

- Python 3.12+ / FastAPI + uvicorn（ASGI サーバー）
- pywebview 6.x（macOS WKWebView ラッパー）
- watchdog（ファイル監視）
- sse-starlette（Server-Sent Events）
- Jinja2（HTML テンプレート）
- htmx + mermaid.js（CDN）
- uv（パッケージ管理）/ PyInstaller（`.app` バンドル）

## コマンド

```bash
uv run task dev        # pywebview アプリを起動
uv run task server     # FastAPI サーバーのみ起動（ブラウザ確認用）
uv run task test       # テスト + カバレッジ
uv run task lint       # Ruff チェック
uv run task format     # Ruff フォーマット
uv run task typecheck  # ty 型チェック
uv run task build      # .app バンドルビルド
```

## コード品質

- **行長**: 100 文字以内（Ruff 強制）
- **複雑度**: 認知的複雑度 ≤ 10（Ruff C901 強制）
- **import 順序**: Ruff I（isort 互換）で自動整理
- **型チェック**: ty（pre-commit フック）
- **テストカバレッジ**: 80% 以上（`fail_under = 80`）

## Python コーディング規約

- 型アノテーションを必ず付ける（引数・戻り値）
- モジュールレベルのシングルトン（`watch_service`, `event_bus`）はテスト時に差し替え可能にする
- `import webview` は関数内でのみ行う（テスト時に pywebview が起動しないよう分離）
- ファイルパスは `backend/paths.py` の定数を使う（`BASE_DIR` / `TEMPLATES_DIR` / `STATIC_DIR`）

## テスト規約

- **ユニットテスト**: `tests/unit/` — pytest AAA スタイル、外部依存なし
- **インテグレーションテスト**: `tests/integration/` — FastAPI `TestClient` 使用
- SSE エンドポイントのテストは `TestClient` の制限からルート登録確認のみ行う
- `uv run pytest tests/unit -q` は 60 秒以内に完了すること

## テンプレートレスポンス

```python
# 正しい（Starlette 1.x 以降）
templates.TemplateResponse(request, "template.html", {"key": "value"})
```

## コミット規約

Conventional Commits + 日本語:

```
feat: Mermaid ビューア画面を追加する
fix: ファイル変更検知が2回通知される問題を修正する
chore: PyInstaller スペックを更新する
```
