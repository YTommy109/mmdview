# ファイル変更検知修正(アトミックセーブ対応 + デバウンス)実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

<!-- derived-from ../specs/2026-06-10-watch-reload-fix-design.md -->

**Goal:** 他アプリのアトミックセーブ(rename 置き換え)やシンボリックリンク経由のパスでもビューアが自動リロードされるようにし、二重リロードをデバウンスで解消する。

**Architecture:** `backend/services/watch_service.py` の `_ChangeHandler` を `on_modified` / `on_created` / `on_moved` 対応に拡張し、resolve 済みパスで比較する。一致イベントは `threading.Timer` によるトレーリングデバウンス(既定 0.2 秒)で 1 回の `bus.notify()` に集約する。SSE・フロントエンドは無変更。

**Tech Stack:** Python 3.12+ / watchdog(FSEventsObserver)/ threading.Timer / pytest

---

## 前提知識

- watchdog はファイルの**親ディレクトリ**を監視する。macOS では FSEvents が使われ、
  イベントパスは**シンボリックリンク解決済みの実パス**(例: `/private/var/...`)で報告される。
- TextEdit 等の macOS アプリは「別ディレクトリの一時ファイルに書いて rename で置き換える」
  アトミックセーブを行う。このときターゲットには `moved`(dest=target)イベントしか来ない。
- FSEvents は rename 置き換え時に偽の `deleted` イベントを合成することがあるため、
  `deleted` はリロード契機にしない。
- テストは実 FS イベントを使うため、イベント到達待ちは `time.sleep` 固定ではなく
  ポーリングで行う(上限 3 秒)。
- コミットはユーザー規約に従い、同一修正に属する変更は push 前なら `--amend` でまとめる。

## ファイル構成

- Modify: `backend/services/watch_service.py` — ハンドラ拡張・デバウンス・stop 時のタイマーキャンセル
- Modify: `tests/unit/test_watch_service.py` — ヘルパー整理 + 新規テスト 4 件

---

### Task 1: テストヘルパーの整理

`_TrackingBus` がテスト関数内に定義されているため、モジュールレベルへ移動し、
通知待ちポーリングヘルパー `_wait_for_notify` を追加する。挙動変更なしのリファクタリング。

**Files:**
- Modify: `tests/unit/test_watch_service.py`

- [ ] **Step 1: ヘルパーを追加し既存テストを書き換える**

`tests/unit/test_watch_service.py` の import 部とファイル末尾の
`test_notify_called_on_file_change` を以下のように変更する:

```python
import time

import pytest

from backend.services.event_bus import EventBus
from backend.services.watch_service import WatchService


class _TrackingBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.notified: list[str] = []

    def notify(self, event: str = "reload") -> None:
        self.notified.append(event)


def _wait_for_notify(bus: _TrackingBus, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bus.notified:
            return True
        time.sleep(0.05)
    return False
```

`test_notify_called_on_file_change` は関数内の `_TrackingBus` 定義と
`from backend.services.event_bus import EventBus` を削除し、こうする:

```python
def test_notify_called_on_file_change(tmp_mmd):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(tmp_mmd))
    tmp_mmd.write_text("graph TD\n    A --> C", encoding="utf-8")
    assert _wait_for_notify(bus)
    svc.stop()
    assert "reload" in bus.notified
```

- [ ] **Step 2: テストが green のままであることを確認する**

Run: `uv run pytest tests/unit/test_watch_service.py -q`
Expected: `7 passed`

- [ ] **Step 3: コミット**

```bash
git add tests/unit/test_watch_service.py
git commit -m "test: watch_service テストのヘルパーをモジュールレベルに整理する"
```

---

### Task 2: アトミックセーブとシンボリックリンクパスの検知

**Files:**
- Modify: `backend/services/watch_service.py:13-23`(`_ChangeHandler`)
- Test: `tests/unit/test_watch_service.py`

- [ ] **Step 1: 失敗するテストを 2 件書く**

`tests/unit/test_watch_service.py` の末尾に追加する。`import os` を import 部に加える:

```python
def test_notify_called_on_atomic_save(tmp_mmd, tmp_path):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(tmp_mmd))
    time.sleep(0.3)  # FSEvents の監視開始を待つ
    staging = tmp_path / "staging"
    staging.mkdir()
    tmp = staging / "new.mmd"
    tmp.write_text("graph TD\n    A --> C", encoding="utf-8")
    os.replace(tmp, tmp_mmd)
    assert _wait_for_notify(bus)
    svc.stop()


def test_notify_called_when_path_contains_symlink(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real_file = real_dir / "test.mmd"
    real_file.write_text("graph TD\n    A --> B", encoding="utf-8")
    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)

    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(link_dir / "test.mmd"))
    time.sleep(0.3)
    real_file.write_text("graph TD\n    A --> C", encoding="utf-8")
    assert _wait_for_notify(bus)
    svc.stop()
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/test_watch_service.py -q`
Expected: `2 failed, 7 passed`(両方とも `assert _wait_for_notify(bus)` で FAIL)

- [ ] **Step 3: `_ChangeHandler` を拡張する**

`backend/services/watch_service.py` の `_ChangeHandler` を以下に置き換える
(デバウンスは Task 3 で入れるため、ここでは直接 notify する):

```python
class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, target: Path, bus: EventBus) -> None:
        # FSEvents はシンボリックリンク解決済みの実パスを報告するため resolve して比較する
        self._target = target.resolve()
        self._bus = bus

    def on_modified(self, event: FileSystemEvent) -> None:
        self._maybe_notify(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        self._maybe_notify(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # アトミックセーブは一時ファイルからの rename 置き換えとして届く
        self._maybe_notify(event.dest_path)

    def _maybe_notify(self, path: str | bytes) -> None:
        if isinstance(path, bytes):
            path = path.decode()
        if Path(path).resolve() == self._target:
            self._bus.notify()
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/test_watch_service.py -q`
Expected: `9 passed`

- [ ] **Step 5: コミット**

```bash
git add backend/services/watch_service.py tests/unit/test_watch_service.py
git commit -m "fix: 他アプリのアトミックセーブでビューアが自動リロードされない問題を修正する"
```

---

### Task 3: デバウンスと stop 時のタイマーキャンセル

**Files:**
- Modify: `backend/services/watch_service.py`(`_ChangeHandler` / `WatchService`)
- Test: `tests/unit/test_watch_service.py`

- [ ] **Step 1: 失敗するテストを 2 件書く**

`tests/unit/test_watch_service.py` の末尾に追加する:

```python
def test_rapid_writes_notify_once(tmp_mmd):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(tmp_mmd))
    time.sleep(0.3)
    for i in range(3):
        tmp_mmd.write_text(f"graph TD\n    A --> C{i}", encoding="utf-8")
    assert _wait_for_notify(bus)
    time.sleep(0.5)  # 追加の通知が来ないことを確認する猶予
    svc.stop()
    assert len(bus.notified) == 1


def test_stop_cancels_pending_notify(tmp_mmd):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus, debounce=1.0)
    svc.set_file(str(tmp_mmd))
    time.sleep(0.3)
    tmp_mmd.write_text("graph TD\n    A --> C", encoding="utf-8")
    # デバウンスタイマーが起動するまで待つ(白箱だが決定的にするため)
    deadline = time.time() + 3.0
    while time.time() < deadline and svc._handler._timer is None:
        time.sleep(0.05)
    assert svc._handler._timer is not None
    svc.stop()
    time.sleep(1.2)
    assert bus.notified == []
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run pytest tests/unit/test_watch_service.py -q`
Expected: 2 件 FAIL —
`test_rapid_writes_notify_once` は `len(bus.notified) == 1` で(直接 notify のため 2 回以上)、
`test_stop_cancels_pending_notify` は `WatchService.__init__` に `debounce` 引数がなく TypeError。

- [ ] **Step 3: デバウンスを実装する**

`backend/services/watch_service.py` 全体を以下に置き換える:

```python
# backend/services/watch_service.py
import threading
import traceback
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.logger import logger
from backend.services.event_bus import EventBus

_DEBOUNCE_SECONDS = 0.2


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, target: Path, bus: EventBus, debounce: float = _DEBOUNCE_SECONDS) -> None:
        # FSEvents はシンボリックリンク解決済みの実パスを報告するため resolve して比較する
        self._target = target.resolve()
        self._bus = bus
        self._debounce = debounce
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        self._maybe_notify(event.src_path)

    def on_created(self, event: FileSystemEvent) -> None:
        self._maybe_notify(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        # アトミックセーブは一時ファイルからの rename 置き換えとして届く
        self._maybe_notify(event.dest_path)

    def _maybe_notify(self, path: str | bytes) -> None:
        if isinstance(path, bytes):
            path = path.decode()
        if Path(path).resolve() != self._target:
            return
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce, self._fire)
            self._timer.daemon = True
            self._timer.start()

    def _fire(self) -> None:
        if self._target.exists():
            self._bus.notify()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class WatchService:
    def __init__(
        self, event_bus: EventBus | None = None, debounce: float = _DEBOUNCE_SECONDS
    ) -> None:
        self._bus = event_bus if event_bus is not None else EventBus()
        self._debounce = debounce
        self._observer: Any = None  # Observer | None; Any avoids watchdog stub limitation
        self._handler: _ChangeHandler | None = None
        self._path: Path | None = None

    def set_file(self, path: str) -> None:
        logger.info("set_file: path=%s", path)
        self.stop()
        self._path = Path(path)
        if not self._path.exists():
            logger.error("set_file: file not found: %s", self._path)
        observer = Observer()
        handler = _ChangeHandler(self._path, self._bus, debounce=self._debounce)
        observer.schedule(handler, str(self._path.parent), recursive=False)
        try:
            observer.start()
        except Exception:
            logger.error("set_file: observer.start() failed:\n%s", traceback.format_exc())
            raise
        self._observer = observer
        self._handler = handler
        logger.info("set_file: watching %s", self._path)

    def get_content(self) -> str | None:
        if self._path is None or not self._path.exists():
            return None
        return self._path.read_text(encoding="utf-8")

    def get_path(self) -> Path | None:
        return self._path

    def stop(self) -> None:
        if self._handler is not None:
            self._handler.cancel()
            self._handler = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run pytest tests/unit/test_watch_service.py -q`
Expected: `11 passed`

- [ ] **Step 5: 全体の品質チェック**

Run: `uv run task test && uv run task lint && uv run task typecheck`
Expected: 全テスト pass(カバレッジ 80% 以上)、lint / typecheck エラーなし

- [ ] **Step 6: Task 2 のコミットに amend で統合する**

Task 2 と同一修正(同じ fix、未 push)のため、ユーザーのコミット規約に従い amend する:

```bash
git add backend/services/watch_service.py tests/unit/test_watch_service.py
git commit --amend --no-edit
```

---

## 検証(実機)

実装完了後、実際のアプリで確認する:

1. `uv run task dev` でアプリを起動し、`.mmd` ファイルを開く
2. 別アプリ(TextEdit / VSCode / vim)でそのファイルを編集・保存する
3. ビューアが自動でリロードされ、変更が反映されることを確認する
