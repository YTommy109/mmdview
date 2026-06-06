# backend/main.py
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.paths import STATIC_DIR
from backend.routers import events, html, update
from backend.services.window_registry import window_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    window_registry.set_loop(asyncio.get_running_loop())
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(html.router)
app.include_router(events.router)
app.include_router(update.router)
