# backend/routers/events.py
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from backend.logger import logger
from backend.services.window_registry import window_registry

router = APIRouter()


@router.get("/events")
async def sse_endpoint(request: Request, window_id: str = "") -> EventSourceResponse:
    async def generator():
        bus = window_registry.get_bus(window_id)
        if bus is None:
            logger.debug("SSE: no bus registered for window_id=%r", window_id)
            return
        q = bus.subscribe()
        try:
            while True:
                event = await q.get()
                yield {"data": event}
        finally:
            bus.unsubscribe(q)

    return EventSourceResponse(generator())
