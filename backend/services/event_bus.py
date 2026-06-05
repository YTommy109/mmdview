import asyncio


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    def notify(self, event: str = "reload") -> None:
        if self._loop is None:
            return
        for q in list(self._listeners):  # ← list() でスナップショットを作成
            self._loop.call_soon_threadsafe(q.put_nowait, event)


event_bus = EventBus()
