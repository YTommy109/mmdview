import traceback
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.logger import logger
from backend.services.event_bus import EventBus
from backend.services.event_bus import event_bus as _default_bus


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, target: Path, bus: EventBus) -> None:
        self._target = target
        self._bus = bus

    def on_modified(self, event: FileSystemEvent) -> None:
        src = event.src_path
        if isinstance(src, bytes):
            src = src.decode()
        if Path(src) == self._target:
            self._bus.notify()


class WatchService:
    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._bus = event_bus or _default_bus
        self._observer: Any = None  # Observer | None; Any avoids watchdog stub limitation
        self._path: Path | None = None

    def set_file(self, path: str) -> None:
        logger.info("set_file: path=%s", path)
        self.stop()
        self._path = Path(path)
        if not self._path.exists():
            logger.error("set_file: file not found: %s", self._path)
        observer = Observer()
        handler = _ChangeHandler(self._path, self._bus)
        observer.schedule(handler, str(self._path.parent), recursive=False)
        try:
            observer.start()
        except Exception:
            logger.error("set_file: observer.start() failed:\n%s", traceback.format_exc())
            raise
        self._observer = observer
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


watch_service = WatchService()
