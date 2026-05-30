# mmdview

Mermaid ダイアグラム（`.mmd` / `.md`）をリアルタイムでプレビューする macOS デスクトップアプリ。

## 機能

- ファイルを開いて Mermaid 図を即座にレンダリング
- ファイルを保存すると自動でプレビューを更新
- ウィンドウの位置・サイズと最後に開いたファイルを記憶
- `⌘O` でファイルダイアログを開く

## 動作要件

- macOS 12 (Monterey) 以降

## インストール（開発環境）

```bash
# 依存関係インストール
uv sync

# アプリ起動
uv run task dev
```

## ビルド（配布用 .app）

```bash
uv run task build
open dist/mmdview.app
```

> **初回起動時の Gatekeeper 対応:**
> Finder で `mmdview.app` を右クリック →「開く」を選択してください。

## 開発

```bash
uv run task server     # FastAPI サーバーのみ起動（http://localhost:8000）
uv run task test       # テスト + カバレッジ
uv run task lint       # Ruff lint
uv run task format     # Ruff フォーマット
uv run task typecheck  # ty 型チェック
```

### pre-commit フックのインストール

```bash
uv run pre-commit install
```

## アーキテクチャ

```
mmdview.app
  ├── FastAPI サーバー（localhost:ランダムポート）
  │   ├── GET /           ← welcome / viewer HTML
  │   ├── POST /open-file ← OS ファイルダイアログ
  │   └── GET /events     ← SSE（ファイル変更通知）
  └── WKWebView（pywebview）
       └── mermaid.js でクライアントサイドレンダリング
```

ファイル変更の通知経路: watchdog → EventBus → SSE → `window.location.reload()`

詳細は [`docs/superpowers/specs/2026-05-30-mmdview-design.md`](docs/superpowers/specs/2026-05-30-mmdview-design.md) を参照。

## ライセンス

MIT
