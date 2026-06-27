# mmdview

macOS 向け Mermaid ダイアグラム・ビューアアプリ。
`.mmd` / `.md` ファイルを監視し、mermaid.js でリアルタイムにプレビューする。

## 機能

- ファイルを開いて Mermaid 図を即座にレンダリング
- Markdown 内の Mermaid コードブロックにも対応
- ファイルを保存すると自動でプレビューを更新（0.2s デバウンス）
- 複数ウィンドウで同時に異なるファイルを表示
- Open Recent メニューで最近開いたファイルに素早くアクセス
- `⌘+` / `⌘-` / `⌘0` でズーム操作
- ファイル削除時にバナーで通知、再作成で自動復帰

## 動作要件

- macOS 14 (Sonoma) 以降

## インストール（開発環境）

```bash
cd MmdviewApp
swift build
```

## ビルド（Xcode）

```bash
cd MmdviewApp
xcodegen generate            # .xcodeproj を生成
xcodebuild build -scheme mmdview
```

## 開発

```bash
cd MmdviewApp
swift build                  # ビルド
swift test                   # テスト
xcodegen generate            # .xcodeproj を再生成
```

## アーキテクチャ

```
mmdview.app (Swift / AppKit + SwiftUI)
  ├── AppDelegate        # ライフサイクル・メニュー・ウィンドウ管理
  ├── FileWatcher        # DispatchSource によるファイル監視（0.2s デバウンス）
  ├── ViewerStore        # @Observable 表示状態（content / error / deleted）
  └── ViewerWebView      # WKWebView（NSViewRepresentable）
        ├── 同梱アセット（viewer.html / mermaid.min.js / markdown-it.min.js / style.css）
        └── JS ブリッジ: evaluateJavaScript("render(content, type)")
```

HTTP・SSE・ポート管理は不要。ファイル変更は
`FileWatcher → ViewerStore → evaluateJavaScript` の同一プロセス内伝搬で反映する。

## 技術スタック

- Swift 6 / AppKit + SwiftUI（macOS 14+）
- WKWebView（mermaid.js / markdown-it.js レンダリング）
- DispatchSource（ファイル監視）
- XcodeGen（プロジェクト生成）/ Swift Package Manager（ビルド）

## ライセンス

MIT
