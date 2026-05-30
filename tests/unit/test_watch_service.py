import time

import pytest

from backend.services.watch_service import WatchService


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
    from backend.services.event_bus import EventBus

    class _TrackingBus(EventBus):
        def __init__(self) -> None:
            super().__init__()
            self.notified: list[str] = []

        def notify(self, event: str = "reload") -> None:
            self.notified.append(event)

    bus = _TrackingBus()
    svc = WatchService(event_bus=bus)
    svc.set_file(str(tmp_mmd))
    tmp_mmd.write_text("graph TD\n    A --> C", encoding="utf-8")
    time.sleep(0.5)
    svc.stop()

    assert "reload" in bus.notified
