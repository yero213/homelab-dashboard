"""FastAPI applicatie voor de server-agent.

Biedt REST endpoints voor OS-info, hardware metrics, opslag en Docker.
Beveiligd met X-API-Key header en voorzien van rate limiting + audit logging.
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from collectors import docker as docker_collector
from collectors import os_info as os_collector
from collectors import system as system_collector

if TYPE_CHECKING:
    from typing import Any

# ─── Logging configuratie ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Laad .env ──────────────────────────────────────────────────────
load_dotenv()

# ─── Configuratie ───────────────────────────────────────────────────
AGENT_API_KEY: str | None = os.getenv("AGENT_API_KEY")
AGENT_HOST = os.getenv("AGENT_HOST", "0.0.0.0")
AGENT_PORT = int(os.getenv("AGENT_PORT", "9100"))

if not AGENT_API_KEY or len(AGENT_API_KEY) < 16:
    raise RuntimeError(
        "AGENT_API_KEY is vereist en moet minstens 16 tekens lang zijn. "
        "Genereer een key met: openssl rand -hex 32"
    )

# ─── CORS origins ───────────────────────────────────────────────────
# Alleen het dashboard (localhost:8000) heeft toegang.
# In productie: voeg de dashboard URL toe.
_CORS_ORIGINS: list[str] = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ─── Rate limiting state (per-IP) ───────────────────────────────────
_request_history: dict[str, list[float]] = {}
_RATE_LIMIT = 100       # max requests per IP
_RATE_WINDOW = 60       # per 60 seconden


def _check_rate_limit(ip: str) -> bool:
    """Per-IP rate limiting met rolling window.

    Houdt per IP een lijst bij van timestamps in de laatste N seconden.
    """
    now = time.time()
    cutoff = now - _RATE_WINDOW

    if ip not in _request_history:
        _request_history[ip] = []

    _request_history[ip] = [t for t in _request_history[ip] if t > cutoff]

    if len(_request_history[ip]) >= _RATE_LIMIT:
        return False  # rate limit exceeded

    _request_history[ip].append(now)
    return True


# ─── Audit logging middleware (als eerste toegepast) ────────────────

async def audit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Middleware die alle requests logt.

    Logt: method, path, IP, status code, duur, en container actie detail.
    """
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    # Voeg container actie-detail toe aan audit log
    path = request.url.path
    detail = ""
    if "/containers/" in path:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            container_id = parts[-2]
            action = parts[-1]
            if action in ("start", "stop", "restart"):
                detail = f" [{action} {container_id}]"

    logger.info(
        "AUDIT: %s %s → %d (%s, %.2fs)%s",
        request.method,
        path,
        response.status_code,
        request.client.host if request.client else "unknown",
        duration,
        detail,
    )
    return response


# ─── API-key middleware (als tweede toegepast) ──────────────────────

async def api_key_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Middleware die elke request valideert met X-API-Key.

    Alleen /health endpoint is vrij toegankelijk.
    Gebruikt secrets.compare_digest() voor timing-attack bescherming.
    """
    # Publieke endpoint(s) — geen API-key nodig
    if request.url.path == "/health":
        return await call_next(request)

    # Rate limiting check (per IP)
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        logger.warning("Rate limit overschreden van %s", ip)
        return Response(
            content='{"error": "rate_limit_exceeded", "message": "Te veel requests. Probeer later opnieuw."}',
            status_code=429,
            media_type="application/json",
        )

    api_key = request.headers.get("X-API-Key")

    if not api_key:
        return Response(
            content='{"error": "unauthorized", "message": "API-key ontbreekt. Voeg X-API-Key header toe."}',
            status_code=401,
            media_type="application/json",
        )

    if not secrets.compare_digest(api_key, AGENT_API_KEY):
        return Response(
            content='{"error": "forbidden", "message": "ongeldige API-key"}',
            status_code=403,
            media_type="application/json",
        )

    return await call_next(request)


# ─── FastAPI app ────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler — vervangt verouderde on_event."""
    logger.info("Agent opgestart op %s:%d", AGENT_HOST, AGENT_PORT)
    yield
    logger.info("Agent afgesloten")


app = FastAPI(
    title="Homelab Dashboard — Server Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware volgorde: CORS (externe laag) → Audit → API-key
# CORS wordt via add_middleware toegevoegd (buitenste laag)
# Audit middleware logt ALLE requests (ook geweigerde)
# API-key middleware valideert daarna
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,  # X-API-Key is geen browser credential
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)
app.middleware("http")(audit_middleware)       # Eerst loggen
app.middleware("http")(api_key_middleware)     # Dan valideren


# ─── Helpers ────────────────────────────────────────────────────────

def _collect_all_metrics() -> dict:
    """Verzamel alle metrics in één dict."""
    return {
        "os": os_collector.collect(),
        "hardware": system_collector.collect_hardware(),
        "storage": system_collector.collect_storage(),
        "containers": docker_collector.list_containers(),
    }


# ─── Endpoints ──────────────────────────────────────────────────────

@app.get("/")
async def root() -> dict:
    """Root endpoint — geeft API-info."""
    return {
        "service": "Homelab Dashboard — Server Agent",
        "version": "1.0.0",
        "endpoints": [
            "/health",
            "/os",
            "/hardware",
            "/storage",
            "/containers",
            "/containers/{id}/{action}",
            "/metrics",
            "/overview",
        ],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Gezondheidscheck — vrij toegankelijk."""
    return {"status": "ok"}


@app.get("/os")
async def get_os_info() -> dict:
    """Geef OS-info (hostname, type, kernel, uptime)."""
    return os_collector.collect()


@app.get("/hardware")
async def get_hardware() -> dict:
    """Geef hardware metrics (CPU%, RAM)."""
    return system_collector.collect_hardware()


@app.get("/storage")
async def get_storage() -> list[dict]:
    """Geef opslaginformatie (schijven, gebruik)."""
    return system_collector.collect_storage()


@app.get("/containers")
async def get_containers() -> list[dict]:
    """Geef lijst van Docker containers (actief + gestopt)."""
    return docker_collector.list_containers()


@app.post("/containers/{container_id}/{action}")
async def perform_container_action(container_id: str, action: str) -> dict:
    """Voer actie uit op een container (start/stop/restart).

    Args:
        container_id: korte of lange container-ID
        action: "start", "stop", of "restart"
    """
    if action not in ("start", "stop", "restart"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_action",
                "message": f"Ongeldige actie '{action}'. Gebruik: start, stop, restart",
            },
        )

    result = docker_collector.container_action(container_id, action)

    if not result["success"]:
        status = 503 if "niet beschikbaar" in result["message"] else 500
        if "niet gevonden" in result["message"]:
            status = 404
        raise HTTPException(status_code=status, detail=result)

    return result


@app.get("/overview")
async def get_overview() -> dict:
    """Combineer alle metrics in één response (voor dashboard proxy)."""
    return _collect_all_metrics()


@app.get("/metrics")
async def get_metrics() -> dict:
    """Alias voor /overview — geeft alle metrics."""
    return _collect_all_metrics()


# ─── Main ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent:app",
        host=AGENT_HOST,
        port=AGENT_PORT,
        reload=False,
        log_level="info",
    )
