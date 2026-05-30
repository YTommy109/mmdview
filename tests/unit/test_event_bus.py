import asyncio

import pytest

from backend.services.event_bus import EventBus


@pytest.fixture
def bus():
    b = EventBus()
    b.set_loop(asyncio.new_event_loop())
    return b


def test_subscribe_returns_queue(bus):
    q = bus.subscribe()
    assert q is not None


def test_notify_puts_event_in_queue(bus):
    loop = asyncio.new_event_loop()
    bus.set_loop(loop)
    q = bus.subscribe()
    bus.notify("reload")
    event = loop.run_until_complete(asyncio.wait_for(q.get(), timeout=1.0))
    assert event == "reload"
    loop.close()


def test_unsubscribe_removes_queue(bus):
    q = bus.subscribe()
    bus.unsubscribe(q)
    assert q not in bus._listeners
