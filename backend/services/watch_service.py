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
        # FSEvents はシンボリックリンク解決済みの実パスを報告するため
        # resolve して比較する
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
        # ファイルが別パスへ移動された場合は削除として扱う
        self._maybe_notify(event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._maybe_notify(event.src_path)

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
        self._bus.notify("reload" if self._target.exists() else "deleted")

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
        # inotify(Linux)はシンボリックリンクを辿らないため、実体の親ディレクトリを監視する
        watch_dir = self._path.resolve().parent
        observer.schedule(handler, str(watch_dir), recursive=False)
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
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        if self._handler is not None:
            self._handler.cancel()
            self._handler = None
