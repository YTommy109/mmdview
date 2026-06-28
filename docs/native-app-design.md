# macOS ネイティブアプリ（Swift） — 設計ドキュメント

**日付**: 2026-06-11
**ステータス**: ドラフト

## 概要

本ドキュメントは **macOS ネイティブアプリ（Swift）** のアーキテクチャ設計書である。

- 現行 mmdview（Python + FastAPI + pywebview）と**同等の機能**を Swift で再実装する
- `.mmd` / `.md` ファイルを監視し、mermaid.js でリアルタイムプレビューする
- Python 版の「ローカル HTTP サーバー + WKWebView」構成は捨て、
  **プロセス内完結**のネイティブ構成にする

---

## 機能パリティ表

現行実装済み仕様と Swift 版での置き換え方針。

| 現行 mmdview（Python） | Swift 版での実現方法 |
|---|---|
| FastAPI + uvicorn（ローカル HTTP） | **廃止**。`WKWebView` に直接 HTML を供給 |
| pywebview ウィンドウ | SwiftUI + `NSWindow`（複数ウィンドウ） |
| watchdog ＋ 0.2 秒デバウンス | `DispatchSource.makeFileSystemObjectSource` ＋ 同等デバウンス |
| SSE による変更通知 | 不要。同一プロセス内で直接 `WKWebView` を更新 |
| Apple Events（odoc）の自前ハンドリング | `NSApplicationDelegate.application(_:open:)` ／ DocumentGroup |
| 最近開いたファイル（自前 JSON・最大 10 件） | `NSDocumentController` 標準機能 |
| ウィンドウ状態復元（window_state.json） | macOS 標準の State Restoration |
| 自動アップデート（GitHub Releases 自前実装） | **Sparkle 2** を採用 |
| ファイル関連付け（Info.plist / UTType） | 現行 `mmdview.spec` の宣言を Info.plist に移植 |
| ズーム（0.5〜2.0、localStorage） | 現行 JS 実装を移植（`UserDefaults` 永続化に変更） |
| Mermaid エラーパネル・削除バナー | 現行 HTML/CSS/JS を移植 |
| PyInstaller バンドル | Xcode ビルド ＋ codesign / notarization |

---

## アーキテクチャ

```
mmdview.app (Swift / SwiftUI)
  ├── App 層           # ライフサイクル・メニュー・ウィンドウ管理
  ├── FileWatcher      # DispatchSource によるファイル監視（0.2s デバウンス）
  ├── ViewerStore      # 表示状態（ファイル内容・エラー・削除フラグ）
  └── ViewerWebView    # WKWebView
        ├── 同梱アセット（viewer.html / mermaid.min.js / markdown-it.min.js / style.css）
        └── JS ブリッジ
             ├── Swift → JS: evaluateJavaScript（本文更新・削除バナー）
             └── JS → Swift: WKScriptMessageHandler（必要時のみ）
```

- HTTP・SSE・ポート管理は不要になる。ファイル変更は
  `FileWatcher → ViewerStore → evaluateJavaScript` の同一プロセス内伝搬で反映する
- **mermaid.js・markdown-it.js と viewer の HTML/CSS/JS** をアプリバンドルに同梱する
  （htmx・SSE 拡張・_hyperscript は不要になる）
- HTML は `WKWebView.loadFileURL`（バンドル内）で読み込み、
  本文は JS 関数 `render(content)` 呼び出しで差し替える
  （現行の `location.reload()` 方式より、ちらつきとスクロール位置リセットがなくなる）

---

## モジュール構成

```
mmdview/
├── App/
│   ├── MmdviewApp.swift        # @main・Settings・メニュー定義
│   ├── AppDelegate.swift       # application(_:open:)・終了処理
│   └── WindowController.swift  # ウィンドウ生成・タイトル・複数ウィンドウ管理
├── Viewer/
│   ├── ViewerStore.swift       # ObservableObject（content / error / deleted）
│   ├── ViewerWebView.swift     # NSViewRepresentable（WKWebView ラッパー）
│   └── Resources/
│       ├── viewer.html         # 現行 viewer.html から移植（SSE 部分を除去）
│       ├── mermaid.min.js
│       ├── markdown-it.min.js
│       └── style.css
├── FileWatching/
│   ├── FileWatcher.swift       # DispatchSource 監視・デバウンス
│   └── Debouncer.swift
└── mmdviewTests/
```

---

## ファイル監視

現行 watchdog 実装の挙動仕様を引き継ぐ。

- 監視対象はファイルの**親ディレクトリ**（エディタの atomic save =
  rename で inode が変わっても追跡できるようにするため。現行と同じ理由）
- シンボリックリンクは実パスに解決してから比較する（現行 `.resolve()` 相当）
- イベント発生から **0.2 秒のデバウンス**後に読み込み・再描画
  （連続保存での多重描画を防ぐ。現行と同じ値）
- ファイル消失時は `deleted` 状態にし、削除バナー＋グレー背景を表示（現行同等）
- 実装は `DispatchSource.makeFileSystemObjectSource`（`.write` イベント、
  ディレクトリ FD 監視）を第一候補とする。ネットワークボリューム対応が
  必要になったら `FSEventStream` に切り替える

---

## ウィンドウ管理・ファイルオープン

- 1 ファイル = 1 ウィンドウの複数ウィンドウ対応（現行同等）。
  ウィンドウごとに `ViewerStore` と `FileWatcher` を持つ
  （現行 `window_registry` の window_id → WatchService/EventBus 対応と同型）
- `File > Open...`（⌘O）・`File > Open Recent` を提供。
  Open Recent は `NSDocumentController.shared.noteNewRecentDocumentURL(_:)` を使い、
  自前の recent_files.json は持たない
- 「このアプリで開く」「Dock へのドロップ」は
  `application(_:open:)` で受ける。現行の Apple Events 自前パッチ
  （`_patch_app_delegate_for_open_file` / `_StartupFileGate`）で解決していた
  起動順序問題は、AppKit 標準のイベント配送に乗ることで解消される
- ファイル関連付けは現行 `mmdview.spec` の宣言（`com.degino.mmdview.mermaid-diagram`、
  拡張子 `mmd` / `mermaid`、`LSHandlerRank` Owner ＋ markdown Alternate）を
  Info.plist にそのまま移植する
- ウィンドウ位置・サイズ・開いていたファイルの復元は macOS 標準の
  State Restoration（`NSWindow.restorationClass`）で行い、
  自前の window_state.json は持たない

---

## 表示仕様の引き継ぎ

viewer.html・style.css・mermaid 初期化設定は現行実装から移植する。

- **mermaid 初期化**: `startOnLoad: false`、全ダイアグラム種別 `useMaxWidth: false`、
  `theme: 'default'`（現行と同一）
- **`.mmd` の扱い**: 全文を `<pre class="mermaid">` に渡し mermaid.js に処理させる
- **`.md` の扱い**: markdown-it.js で markdown → HTML 変換する。
  ` ```mermaid ` フェンスは markdown-it のカスタムレンダラーで `<pre class="mermaid">` に出力し、
  mermaid.js が SVG 描画する（Web アプリの markdown-it-py と同ファミリーで挙動が揃う）
- **ズーム**: 0.5〜2.0（ボタン・キーは 25% 刻み、ホイールは連続）、基準スケール 0.75、
  `Cmd +/-`・`Ctrl + ホイール`・%表示クリックでリセット。
  永続化は localStorage から `UserDefaults` に変更（ウィンドウ間で共有）
- **エラーパネル**: `mermaid.parseError` で構文エラーの詳細メッセージを
  赤ボーダー・等幅フォントのパネルに表示（現行同等）
- **削除バナー**: ファイル削除時にグレーバナー＋背景色変更（現行同等）

---

## 自動アップデート

現行の自前実装（GitHub Releases API 照合 → DMG ダウンロード → hdiutil マウント →
シェルスクリプトでアプリ置換）は **Sparkle 2 に置き換える**。

| 観点 | 自前実装（現行） | Sparkle 2（採用） |
|---|---|---|
| 実装・保守コスト | DMG マウント・置換スクリプトを自前保守 | フレームワークに委譲 |
| 署名検証 | なし | EdDSA 署名検証あり |
| 配信 | GitHub Releases（latest API） | appcast.xml（GitHub Pages / Releases に配置） |
| UI | htmx 製の独自ダイアログ | 標準の更新ダイアログ |

リリース CI で appcast.xml の生成・署名を行う。配布には codesign + notarization を
必須とする（Sparkle の差し替え更新は署名済みアプリが前提のため）。

### セットアップ詳細

#### SUFeedURL（appcast.xml）の配置場所

| 方式 | 利点 | 欠点 |
|---|---|---|
| GitHub Releases assets | リリース CI と同一ワークフローで完結する。CDN（Fastly）経由で配信される。追加のリポジトリ設定・デプロイステップが不要 | URL が GitHub のアセット形式になる（`/releases/download/latest/appcast.xml`）。GitHub の可用性に依存する |
| GitHub Pages | 独自ドメインを設定できる。URL が短く安定する（`https://degino.github.io/mmdview/appcast.xml`） | Pages 用ブランチまたはリポジトリの管理が追加で必要。リリース CI から Pages へのデプロイステップを別途組む必要がある |

**推奨: GitHub Releases assets**

理由:

- 現行のリリース CI（`v*` タグ → DMG ビルド → `softprops/action-gh-release`）に
  `generate_appcast` の実行と appcast.xml のアップロードを追加するだけで済む
- DMG と appcast.xml が同一 Release に紐づくため、成果物の一貫性が保たれる
- GitHub Releases は Fastly CDN 経由で配信されるため、追加の CDN 設定は不要
- Pages 用のブランチ管理やデプロイ設定などの追加インフラが不要

Info.plist に設定する `SUFeedURL` の値:

```
https://github.com/user/mmdview/releases/latest/download/appcast.xml
```

`/releases/latest/download/` は最新 Release のアセットに 302 リダイレクトされるため、
バージョンごとに URL を更新する必要がない。

#### EdDSA 署名鍵の管理方法

Sparkle 2 は更新アーカイブの真正性検証に **EdDSA（Ed25519）署名** を使用する。

**鍵の生成:**

```bash
# Sparkle 同梱の generate_keys を一度だけ実行する
./bin/generate_keys
```

このコマンドは以下を行う:

- EdDSA 秘密鍵を macOS の**ログインキーチェーン**に保存する
- 対応する Base64 エンコード済み公開鍵を標準出力に表示する

表示された公開鍵を Info.plist の `SUPublicEDKey` に設定する。

**秘密鍵の保管場所:**

| 保管先 | 用途 |
|---|---|
| 開発者のログインキーチェーン | ローカルでの `sign_update` / `generate_appcast` 実行用 |
| GitHub Actions Secret（`SPARKLE_PRIVATE_KEY`） | CI での自動署名用。`generate_keys -x` でエクスポートした値を格納する |

**推奨: GitHub Actions Secret**

理由:

- リリースは CI で自動実行されるため、CI 環境から秘密鍵にアクセスできる必要がある
- Actions Secret は暗号化保存され、ログに出力されない
- `generate_keys -x` で既存の鍵をエクスポートし、`-f` でインポートできるため、
  ローカルと CI 間の鍵共有が可能

**CI での署名フロー概要:**

```
v* タグ push
  → リリース CI 起動
    → .app ビルド（codesign + notarization）
    → DMG 作成
    → SPARKLE_PRIVATE_KEY を環境変数にセット
    → sign_update で DMG に EdDSA 署名を生成
    → generate_appcast で appcast.xml を生成（署名情報を自動埋め込み）
    → DMG + appcast.xml を GitHub Release に添付
```

`sign_update` は DMG のパスを受け取り、`sparkle:edSignature` と `length` を含む
XML フラグメントを出力する。`generate_appcast` はこの署名を appcast.xml の
`<enclosure>` 要素に自動的に埋め込む。

#### 初回起動時の自動確認ダイアログ設定

Sparkle の `SUEnableAutomaticChecks` は、自動アップデート確認の初期動作を制御する。

| 設定値 | 動作 |
|---|---|
| 未設定（デフォルト） | 初回起動時は何もしない。**2 回目の起動時**にユーザーへ自動確認の許可ダイアログを表示する |
| `YES` | 許可ダイアログを表示せず、最初から自動確認を有効にする |
| `NO` | 許可ダイアログを表示せず、自動確認を無効にする（手動確認のみ） |

**推奨: 未設定（デフォルト動作）**

理由:

- 初回起動時にダイアログを出さないことで、ファーストランの体験を損なわない
  （Sparkle のデフォルト設計意図と一致する）
- 2 回目の起動でユーザーに判断を委ねることで、自動通信への同意を明示的に得られる
- `YES` に設定するとユーザーの同意なく外部通信が発生するため、
  プライバシーの観点で避けるべきである
- mmdview はローカル完結のビューアアプリであり、ネットワーク通信はアップデート確認のみ。
  ユーザーが自覚的に選択できるデフォルト動作が適切である

関連する Info.plist キー:

| キー | デフォルト値 | 説明 |
|---|---|---|
| `SUFeedURL` | — | appcast.xml の URL（必須） |
| `SUPublicEDKey` | — | EdDSA 公開鍵（必須） |
| `SUEnableAutomaticChecks` | 未設定 | 上記の通り |
| `SUScheduledCheckInterval` | `86400`（24 時間） | 自動確認の間隔（秒）。変更不要 |
| `SUAutomaticallyUpdate` | `NO` | `YES` にするとバックグラウンドで自動インストールする。当面 `NO` を維持 |

---

## 技術スタック

| 技術 | 用途 |
|---|---|
| Swift 6 / SwiftUI + AppKit | アプリ本体（macOS 14+） |
| WKWebView | markdown・mermaid レンダリング |
| mermaid.min.js（同梱） | Mermaid SVG レンダリング（現行のキャッシュ版を流用） |
| markdown-it.min.js（同梱） | `.md` ファイルの markdown → HTML 変換 |
| Sparkle 2 (SPM) | 自動アップデート |
| XCTest | ユニット・UI テスト |

依存管理は Swift Package Manager。プロジェクト生成に XcodeGen 等を使うかは
実装開始時に決める。

---

## テスト方針

現行の「ロジックは厚く、GUI/OS 層は薄く」の方針を踏襲する。

- **ユニットテスト（XCTest）**: FileWatcher（デバウンス・atomic save・シンボリックリンク・
  削除検知）、Debouncer、ViewerStore の状態遷移。現行 `test_watch_service.py` の
  テストケースを移植する
- **WebView 連携**: viewer.html の JS（ズーム・エラーパネル）は現行 Playwright e2e の
  ケースを `WKWebView` ＋ XCTest で再現する
- **GUI/OS 層**（メニュー・State Restoration・Sparkle）: 自動テスト対象外とし、
  リリース前の手動チェックリストで担保する（現行のカバレッジ除外方針と同じ）

---

## リリース計画

1. 現行 Python 版は期待通りに動作していないことが Swift 版への移行動機であり、
   並行メンテナンスは行わない
2. Swift 版が動作し始め次第、GitHub Releases の既存バイナリを削除して置き換える
   （Sparkle 移行のため、初回は手動での入れ替えインストールになる）

---

## スコープ外

- Windows / Linux 対応
- mermaid 以外のダイアグラム形式
- エクスポート機能（SVG / PNG）
- テキスト編集機能（ビューア専用アプリ）
- AI 編集機能
