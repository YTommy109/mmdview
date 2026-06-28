# native-app-design.md — 設計レビュー TODO

## Important（実装前に決定必要）

- [x] **サンドボックス・エンタイトルメント方針を決定する**
  - App Sandbox は無効（App Store 外配布、ファイル監視に広範なアクセスが必要）
  - entitlements は空（Hardened Runtime のみ有効化）
  - Sandbox 対応が必要になった場合は security-scoped bookmark を追加する

- [x] **JS ブリッジの `render()` インターフェース仕様を定義する**
  - `render(content, type)` — 単一関数、`type` は `"mmd"` or `"md"`
  - `.mmd`: 全文を `<pre class="mermaid">` に渡す
  - `.md`: markdown-it.js で変換、`mermaid` フェンスは `<pre class="mermaid">` に出力
  - エラーハンドリング: `.mmd` はエラーパネル表示＋ダイアグラム非表示、
    `.md` はエラーパネル表示＋他のコンテンツは維持

- [x] **`loadFileURL` と JS リソース参照方式を決定する**
  - viewer.html から mermaid.min.js / markdown-it.min.js を外部ファイル参照
  - `WKWebView.loadFileURL(_:allowingReadAccessTo:)` の `allowingReadAccessTo` は
    viewer.html の親ディレクトリ（Resources/）をスコープとする

- [x] **`.md` の `LSHandlerRank: Alternate` の意図を明記する**
  - Alternate を維持：既存エディタのデフォルトを上書きしない意図
  - `net.ia.markdown` UTI（MindNode 等）に対しても Alternate で登録済み

## Minor（実装開始前に記述推奨）

- [x] **Sparkle 2 のセットアップ詳細を設計書に追記する**
  - SUFeedURL の配置場所（GitHub Pages か GitHub Releases assets か）
  - EdDSA 鍵の管理方法（GitHub Actions Secret 等）
  - 初回起動時の自動確認ダイアログ設定（`SUEnableAutomaticChecks` の初期値）

- [x] **`FileWatcher` の actor 設計を決定する**
  - `@unchecked Sendable` + 内部シリアル `DispatchQueue` で手動スレッド安全性を保証
  - ファイル FD（`.write` / `.delete` / `.rename`）+ ディレクトリ FD（`.write`）の
    二重監視で in-place 変更と atomic save の両方を検知
  - MainActor へのコールバックは `Task { @MainActor in }` で送出

- [ ] **WebView JS テスト方針を事前検証する**
  - XCTest で headless WKWebView が安定するか確認する
  - ズーム計算・エラーパネル表示条件など純粋なロジックは
    Jest（Node.js）で単体テストする選択肢も検討する

- [x] **`evaluateJavaScript` のレースコンディション対策を設計する**
  - `WKNavigationDelegate.didFinish` で `isReady` フラグを立てる
  - `isReady` 前の更新は `pendingUpdate` クロージャにキューイング
  - `didFinish` 発火時に `pendingUpdate` を実行
  - 同一コンテンツの重複レンダリングは `lastRenderedContent` で抑制
