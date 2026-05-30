from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from backend.services.event_bus import event_bus

router = APIRouter()


@router.get("/events")
async def sse_endpoint(request: Request) -> EventSourceResponse:
    async def generator():
        q = event_bus.subscribe()
        try:
            while True:
                event = await q.get()
                yield {"data": event}
        finally:
            event_bus.unsubscribe(q)

    return EventSourceResponse(generator())
