import os
import time

import pytest
from watchdog.events import FileCreatedEvent, FileDeletedEvent, FileMovedEvent

from backend.services.event_bus import EventBus
from backend.services.watch_service import WatchService, _ChangeHandler


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


@pytest.fixture
def tmp_mmd(tmp_path):
    f = tmp_path / "test.mmd"
    f.write_text("graph TD\n    A --> B", encoding="utf-8")
    return f


def test_get_content_returns_none_when_no_file():
    svc = WatchService()
    assert svc.get_content() is None


def test_get_path_returns_none_when_no_file():
    svc = WatchService()
    assert svc.get_path() is None


def test_set_file_reads_content(tmp_mmd):
    svc = WatchService()
    svc.set_file(str(tmp_mmd))
    assert svc.get_content() == "graph TD\n    A --> B"
    svc.stop()


def test_set_file_sets_path(tmp_mmd):
    svc = WatchService()
    svc.set_file(str(tmp_mmd))
    assert svc.get_path() == tmp_mmd
    svc.stop()


def test_set_file_starts_observer(tmp_mmd):
    svc = WatchService()
    svc.set_file(str(tmp_mmd))
    assert svc._observer is not None
    assert svc._observer.is_alive()
    svc.stop()


def test_stop_kills_observer(tmp_mmd):
    svc = WatchService()
    svc.set_file(str(tmp_mmd))
    svc.stop()
    assert svc._observer is None


def test_notify_called_on_file_change(tmp_mmd):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(tmp_mmd))
    tmp_mmd.write_text("graph TD\n    A --> C", encoding="utf-8")
    assert _wait_for_notify(bus)
    svc.stop()
    assert "reload" in bus.notified


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


def test_handler_on_moved_to_target_notifies(tmp_mmd):
    bus = _TrackingBus()
    handler = _ChangeHandler(tmp_mmd, bus, debounce=0.01)
    handler.on_moved(FileMovedEvent(str(tmp_mmd.parent / ".tmp123"), str(tmp_mmd)))
    assert _wait_for_notify(bus)
    assert bus.notified == ["reload"]


def test_handler_on_created_target_notifies(tmp_mmd):
    bus = _TrackingBus()
    handler = _ChangeHandler(tmp_mmd, bus, debounce=0.01)
    handler.on_created(FileCreatedEvent(str(tmp_mmd)))
    assert _wait_for_notify(bus)
    assert bus.notified == ["reload"]


def test_rapid_writes_notify_once(tmp_mmd):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(tmp_mmd))
    time.sleep(0.5)  # 監視開始直後のイベントが落ち着くまで待つ
    bus.notified.clear()  # 監視開始直後に発生するスタートアップイベントの通知を除外する
    # デバウンス窓内の連続書き込みは 1 回の通知に集約される
    for i in range(3):
        tmp_mmd.write_text(f"graph TD\n    A --> C{i}", encoding="utf-8")
        time.sleep(0.05)  # デバウンス窓(0.2 秒)内に収まる間隔で書き込む
    assert _wait_for_notify(bus)
    time.sleep(0.5)  # デバウンス満了後に追加の通知が来ないことを確認する猶予
    svc.stop()
    assert len(bus.notified) == 1


def test_stop_cancels_pending_notify(tmp_mmd):
    bus = _TrackingBus()
    svc = WatchService(event_bus=bus, debounce=1.0)
    svc.set_file(str(tmp_mmd))
    time.sleep(0.3)
    tmp_mmd.write_text("graph TD\n    A --> C", encoding="utf-8")
    # デバウンスタイマーが起動するまで待つ(白箱だが決定的にするため)
    handler = svc._handler
    assert handler is not None
    deadline = time.time() + 3.0
    while time.time() < deadline and handler._timer is None:
        time.sleep(0.05)
    assert handler._timer is not None
    svc.stop()
    time.sleep(1.2)
    assert bus.notified == []


def test_fire_notifies_deleted_when_file_missing(tmp_mmd):
    bus = _TrackingBus()
    handler = _ChangeHandler(tmp_mmd, bus, debounce=0.01)
    tmp_mmd.unlink()
    handler._fire()
    assert bus.notified == ["deleted"]


def test_handler_on_deleted_target_notifies_deleted(tmp_mmd):
    bus = _TrackingBus()
    handler = _ChangeHandler(tmp_mmd, bus, debounce=0.01)
    tmp_mmd.unlink()
    handler.on_deleted(FileDeletedEvent(str(tmp_mmd)))
    assert _wait_for_notify(bus)
    assert bus.notified == ["deleted"]


def test_handler_on_moved_away_notifies_deleted(tmp_mmd, tmp_path):
    bus = _TrackingBus()
    handler = _ChangeHandler(tmp_mmd, bus, debounce=0.01)
    new_path = tmp_path / "renamed.mmd"
    tmp_mmd.rename(new_path)
    handler.on_moved(FileMovedEvent(str(tmp_mmd), str(new_path)))
    assert _wait_for_notify(bus)
    assert bus.notified == ["deleted"]
