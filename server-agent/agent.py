"""Server Agent — draait op elke machine en exposeert een REST API.

UmbrelOS: draait als Docker-container (zie Dockerfile).
Ubuntu:   draait als systemd-service of rechtstreeks met uvicorn.

Endpoints:
  GET  /overview          — alles in één request
  GET  /os                — OS-info (hostname, type, kernel, uptime)
  GET  /storage           — schijfruimte
  GET  /hardware          — CPU / RAM metrics
  GET  /docker            — lijst Docker containers
  POST /docker/<id>/start — start container
  POST /docker/<id>/stop  — stop container
  POST /docker/<id>/restart — herstart container
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from collectors import docker as docker_collector
from collectors import os_info as os_collector
from collectors import system as system_collector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent")

# ─── Security ────────────────────────────────────────────────────────
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "dev-agent-key")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_key(api_key: str = Security(api_key_header)) -> str:
    if api_key is None or api_key != AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ongeldige API-key",
        )
    return api_key


# ─── App ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agent gestart — key: %s", AGENT_API_KEY[:4] + "...")
    yield
    logger.info("Agent gestopt")


app = FastAPI(
    title="Server Agent",
    version="0.1.0",
    lifespan=lifespan,
)


# ─── Endpoints ───────────────────────────────────────────────────────


@app.get("/overview")
async def get_overview(_: str = Security(verify_key)):
    """Gecombineerd overzicht: OS + storage + hardware + docker."""
    return {
        "os": os_collector.collect(),
        "storage": system_collector.collect_storage(),
        "hardware": system_collector.collect_hardware(),
        "docker_containers": docker_collector.list_containers(),
    }


@app.get("/os")
async def get_os(_: str = Security(verify_key)):
    return os_collector.collect()


@app.get("/storage")
async def get_storage(_: str = Security(verify_key)):
    return system_collector.collect_storage()


@app.get("/hardware")
async def get_hardware(_: str = Security(verify_key)):
    return system_collector.collect_hardware()


@app.get("/docker")
async def get_docker(_: str = Security(verify_key)):
    return {"containers": docker_collector.list_containers()}


@app.post("/docker/{container_id}/{action}")
async def docker_action(
    container_id: str,
    action: str,
    _: str = Security(verify_key),
):
    valid = {"start", "stop", "restart"}
    if action not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ongeldige actie '{action}'",
        )
    result = docker_collector.container_action(container_id, action)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["message"],
        )
    return result


# ─── Startup ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_PORT", "9100"))
    uvicorn.run("agent:app", host=host, port=port, reload=True)
