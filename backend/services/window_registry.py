# backend/services/window_registry.py
import asyncio
from dataclasses import dataclass
from pathlib import Path

from backend.services.event_bus import EventBus
from backend.services.watch_service import WatchService


@dataclass
class _Entry:
    watch: WatchService
    bus: EventBus


class WindowRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def create(self, window_id: str, file_path: str | None = None) -> None:
        if window_id in self._entries:
            self.remove(window_id)
        bus = EventBus()
        if self._loop is not None:
            bus.set_loop(self._loop)
        watch = WatchService(event_bus=bus)
        if file_path:
            watch.set_file(file_path)
        self._entries[window_id] = _Entry(watch=watch, bus=bus)

    def get_watch(self, window_id: str) -> WatchService | None:
        entry = self._entries.get(window_id)
        return entry.watch if entry else None

    def get_bus(self, window_id: str) -> EventBus | None:
        entry = self._entries.get(window_id)
        return entry.bus if entry else None

    def remove(self, window_id: str) -> None:
        entry = self._entries.pop(window_id, None)
        if entry:
            entry.watch.stop()

    def find_by_path(self, path: str) -> str | None:
        p = Path(path)
        for wid, entry in self._entries.items():
            if entry.watch.get_path() == p:
                return wid
        return None

    def snapshot(self) -> list[tuple[str, Path | None]]:
        return [(wid, entry.watch.get_path()) for wid, entry in self._entries.items()]


window_registry = WindowRegistry()
