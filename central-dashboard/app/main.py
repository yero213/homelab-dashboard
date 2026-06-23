"""FastAPI applicatie voor het centrale dashboard.

Verzamelt data van alle server-agents en serveert de frontend.
Beveiligd met DASHBOARD_API_KEY voor API endpoints.
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import router as api_router
from app.services.agent_service import AgentManager

# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Laad .env ──────────────────────────────────────────────────────
load_dotenv()

# ─── Configuratie ──────────────────────────────────────────────────
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8000"))
DASHBOARD_API_KEY: str | None = os.getenv("DASHBOARD_API_KEY")

if not DASHBOARD_API_KEY or len(DASHBOARD_API_KEY) < 16:
    raise RuntimeError(
        "DASHBOARD_API_KEY is vereist en moet minstens 16 tekens lang zijn. "
        "Genereer een key met: openssl rand -hex 32"
    )

# ─── Agents configuratie uit .env ───────────────────────────────────
# Zoekt naar AGENT_<NAAM>_URL en AGENT_<NAAM>_KEY patronen
def _load_agent_configs() -> dict[str, dict]:
    """Lees agent configuraties uit omgevingsvariabelen.

    Herkent AGENT_<ID>_URL en AGENT_<ID>_KEY patronen.
    Voorbeeld: AGENT_UMBRELOS_URL, AGENT_UMBRELOS_KEY
    """
    configs: dict[str, dict] = {}
    for key, value in os.environ.items():
        if key.startswith("AGENT_") and key.endswith("_URL"):
            agent_id = key[6:-4].lower()  # AGENT_ + ID + _URL
            url = value
            api_key = os.getenv(f"AGENT_{agent_id.upper()}_KEY", "")

            if not api_key:
                logger.warning(
                    "Geen API-key gevonden voor agent '%s' (AGENT_%s_KEY ontbreekt)",
                    agent_id, agent_id.upper(),
                )
                continue

            configs[agent_id] = {
                "name": agent_id.capitalize(),
                "url": url,
                "api_key": api_key,
            }
            logger.info("Agent '%s' geconfigureerd: %s", agent_id, url)

    if not configs:
        logger.warning(
            "Geen agents geconfigureerd! Voeg AGENT_<ID>_URL en AGENT_<ID>_KEY "
            "toe aan .env bestand."
        )

    return configs


# ─── API-key middleware ────────────────────────────────────────────

async def api_key_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Middleware voor dashboard API-key verificatie.

    GET-requests (data opvragen) zijn vrij toegankelijk voor het frontend.
    POST/PUT/DELETE (container acties) vereisen een geldige API-key.
    """
    # Publieke paden — altijd vrij toegankelijk
    if request.url.path in ("/health", "/"):
        return await call_next(request)

    # Statische bestanden — vrij toegankelijk
    if request.url.path.startswith("/static/") or request.url.path.startswith("/css/") or \
       request.url.path.startswith("/js/") or request.url.path.startswith("/manifest.json"):
        return await call_next(request)

    # GET-requests zijn vrij toegankelijk (dashboard-data bekijken)
    if request.method == "GET":
        return await call_next(request)

    # POST/PUT/DELETE — vereisen API-key (container acties etc.)
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        return Response(
            content='{"error": "unauthorized", "message": "API-key ontbreekt. Voeg X-API-Key header toe voor schrijfacties."}',
            status_code=401,
            media_type="application/json",
        )

    if not secrets.compare_digest(api_key, DASHBOARD_API_KEY):
        return Response(
            content='{"error": "forbidden", "message": "Ongeldige API-key."}',
            status_code=403,
            media_type="application/json",
        )

    return await call_next(request)


# ─── FastAPI app ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler — initialiseer agent manager."""
    # Laad agent configuraties
    server_configs = _load_agent_configs()

    # Maak AgentManager met alle geconfigureerde agents
    agents: dict[str, tuple[str, str]] = {}
    for sid, cfg in server_configs.items():
        agents[sid] = (cfg["url"], cfg["api_key"])

    manager = AgentManager(agents)

    # Sla op in app.state voor toegang vanuit routers
    app.state.agent_manager = manager
    app.state.server_configs = server_configs

    logger.info(
        "Dashboard opgestart op %s:%d met %d agent(s)",
        DASHBOARD_HOST, DASHBOARD_PORT, len(server_configs),
    )

    yield

    # Cleanup
    await manager.close_all()
    logger.info("Dashboard afgesloten")


app = FastAPI(
    title="Homelab Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── Middleware ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)
app.middleware("http")(api_key_middleware)

# ─── Routes (eerst) ────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Gezondheidscheck."""
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint — serveert de frontend of geeft API-info."""
    index_path = static_dir / "index.html" if static_dir.exists() else None
    if index_path and index_path.is_file():
        from fastapi.responses import HTMLResponse
        return HTMLResponse(index_path.read_text())
    return {
        "service": "Homelab Dashboard",
        "version": "1.0.0",
        "endpoints": [
            "/health",
            "/api/servers",
            "/api/servers/{id}/overview",
            "/api/servers/{id}/os",
            "/api/servers/{id}/hardware",
            "/api/servers/{id}/storage",
            "/api/servers/{id}/containers",
            "/api/servers/{id}/containers/{cid}/{action}",
            "/api/dashboard",
        ],
    }


# ─── Frontend config endpoint ─────────────────────────────────────
# Serveert de API-key aan de frontend (zelfde-origin, beschermd door CORS).
@app.get("/static/js/config.js", include_in_schema=False)
async def js_config():
    """Dynamische JS-configuratie met de API-key voor de frontend."""
    content = f"""// Homelab Dashboard — frontend configuratie
const DASHBOARD_API_KEY = '{DASHBOARD_API_KEY}';
const DASHBOARD_REFRESH_INTERVAL = 30000;
"""
    from fastapi.responses import Response as FastResponse
    return FastResponse(content=content, media_type="application/javascript")


# ─── Statische bestanden (frontend) — op /static/ prefix ──────────
# In Fase 4 worden hier de HTML, CSS en JS bestanden geplaatst.
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info("Statische bestanden beschikbaar via /static/")
else:
    logger.warning("Geen statische bestanden gevonden in: %s", static_dir)


# ─── Entrypoint ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=DASHBOARD_HOST,
        port=DASHBOARD_PORT,
        reload=False,
        log_level="info",
    )
