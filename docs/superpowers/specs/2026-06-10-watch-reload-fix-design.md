# ファイル変更検知の修正設計 — アトミックセーブ対応とデバウンス

<!-- constrained-by ./2026-05-30-mmdview-design.md#データフロー -->

## 背景と問題

mmdview はビューア専用アプリであり、ファイルの編集は他のアプリ(エディタ)で行われる。
既存の watchdog → EventBus → SSE → `location.reload()` パイプラインは存在するが、
**他のアプリで保存してもビューアに反映されない**。

## 根本原因(診断スクリプトによる実証済み)

watchdog の `FSEventsObserver` を用いた保存パターン別の検証で、以下の 2 つの欠陥を確認した。

1. **アトミックセーブが検知できない**
   `_ChangeHandler` は `on_modified` のみ処理している。TextEdit など NSDocument 系
   macOS アプリの標準保存(別ディレクトリの一時ファイルを rename で置き換え)では、
   ターゲットパスに対して `moved`(dest=target)/ `created` イベントしか発生せず、
   通知が 1 回も発火しない。vim のデフォルト保存(バックアップへ rename → 新規作成)も同様。
2. **パス比較がシンボリックリンクで不一致になる**
   FSEvents はシンボリックリンクを解決した実パスでイベントを報告するため、
   `Path(src) == self._target` の比較が `/var/...` vs `/private/var/...` のような
   ケースで失敗する。

副次的問題として、直接書き込みでは `modified` イベントが連発し **通知が 2 回発火**
(二重リロード)することも確認した。

## 設計(案 A: イベントハンドラ拡張 + resolve 比較 + デバウンス)

変更は `backend/services/watch_service.py` に閉じる。SSE・フロントエンドは無変更。

### `_ChangeHandler` の拡張

- `on_modified` / `on_created` は `event.src_path` を、`on_moved` は `event.dest_path` を
  共通の `_maybe_notify(path)` に渡す。
- ターゲットパスはハンドラ生成時に `resolve()` して保持し、イベントパスも
  `resolve()`(非 strict)してから比較する。
- `deleted` イベントは扱わない(FSEvents は rename 置き換え時に偽の `deleted` を
  合成するため、削除をリロード契機にしない)。

### デバウンス

- 一致イベントの度に `threading.Timer`(既定 0.2 秒)を再スタートする
  (トレーリングデバウンス)。
- タイマー満了時、ターゲットファイルが**存在する場合のみ** `bus.notify()` を呼ぶ
  (本当に削除された場合はリロードしない)。
- デバウンス間隔はコンストラクタ引数で注入可能にし、テストで調整できるようにする。
- `WatchService.stop()` は保留中のタイマーをキャンセルする(stop 後の通知や
  テスト間リークを防ぐ)。

### 互換性

- `WatchService.get_path()` / `get_content()` の挙動は変更しない(`self._path` は
  与えられたパスのまま保持)。`window_registry.find_by_path()` の比較に影響を
  与えないため、resolve 済みパスはハンドラ内部でのみ使用する。
- `EventBus.notify()` は `call_soon_threadsafe` を使用しておりタイマースレッドから
  呼んでも安全。

## エラー処理

- タイマー満了時にファイルが存在しない → 通知しない(現状維持で次のイベントを待つ)。
- イベントパスの `resolve()` 失敗はあり得ない(非 strict は例外を投げない)。

## テスト計画(TDD、`tests/unit/test_watch_service.py` に追加)

1. アトミックセーブ(別ディレクトリからの `os.replace`)で notify が呼ばれる。
2. シンボリックリンクを含むパスで `set_file` しても、実パスへの書き込みで notify が呼ばれる。
3. 連続書き込みでも notify は 1 回に集約される(デバウンス)。
4. `stop()` 後は保留タイマーが発火しない。
5. 既存テスト(直接書き込みで notify)は引き続き green であること。

各テストは実 FS イベントを用い、待機はポーリングで上限 2 秒程度。
`uv run pytest tests/unit -q` の 60 秒制限を守る。

## 影響範囲

- 変更ファイル: `backend/services/watch_service.py`、`tests/unit/test_watch_service.py`
- 影響を受ける利用箇所: `WindowRegistry.create()`(ウィンドウごとの監視)— API 変更なし
