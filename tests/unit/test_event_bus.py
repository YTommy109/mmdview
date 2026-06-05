import asyncio
from unittest.mock import patch

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


def test_notify_uses_snapshot_so_unsubscribe_during_iteration_is_safe():
    """notify() はリスナーリストのコピーを反復するため、
    反復中に unsubscribe() が呼ばれても RuntimeError が発生せず
    全リスナーに通知が届く。"""
    loop = asyncio.new_event_loop()
    b = EventBus()
    b.set_loop(loop)

    q1 = b.subscribe()
    b.subscribe()  # 2 番目のリスナー（削除されないほうの確認用）

    delivered: list[str] = []
    original_call_soon = loop.call_soon_threadsafe

    def intercepting_call_soon(fn, arg):
        if len(delivered) == 0:
            b.unsubscribe(q1)  # 1 回目の通知中にリスナーを削除
        delivered.append(arg)
        original_call_soon(fn, arg)

    with patch.object(loop, "call_soon_threadsafe", side_effect=intercepting_call_soon):
        b.notify("reload")  # RuntimeError が出ないこと + 全リスナーに届くこと

    assert len(delivered) == 2, f"Expected 2 deliveries, got {len(delivered)}"
    loop.close()
