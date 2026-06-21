"""FastAPI entrypoint voor de Central Dashboard server.

Start met:
    uvicorn app.main:app --reload --port 8000
Of via Docker (zie Dockerfile).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import HOST, PORT
from .routers import auth as auth_router
from .routers import docker as docker_router
from .routers import servers as servers_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Homelab Dashboard",
    version="0.1.0",
    description="Centrale Web GUI voor homelab-serverbeheer",
)

# ─── API routes ──────────────────────────────────────────────────────
app.include_router(servers_router.router)
app.include_router(docker_router.router)

# ─── Frontend statische bestanden ────────────────────────────────────
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")

logger.info("Dashboard start op %s:%s", HOST, PORT)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
