"""ReplayForge API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from replayforge_api.config import get_settings
from replayforge_api.db import init_db
from replayforge_api.routes.api import router
from replayforge_api.services import orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    orchestrator.resume_incomplete()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ReplayForge", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[get_settings().web_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
    )
    app.include_router(router)
    return app


app = create_app()
