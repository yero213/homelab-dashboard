"""API routers voor het dashboard.

Biedt endpoints die de frontend van data voorzien door
te proxyn naar de server-agents.

Gebruikt FastAPI dependency injection voor toegang tot
de AgentManager (opgeslagen in app.state).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models import AgentOverview, ContainerInfo, HardwareMetrics, OSInfo, StorageInfo
from app.services.agent_service import AgentManager

logger = logging.getLogger(__name__)

# ─── Router setup ──────────────────────────────────────────────────
router = APIRouter(prefix="/api")


# ─── Dependency: AgentManager uit app.state ────────────────────────

async def get_manager(request: Request) -> AgentManager:
    """FastAPI dependency — geeft de AgentManager uit app.state."""
    manager: AgentManager = request.app.state.agent_manager
    return manager


async def get_server_configs(request: Request) -> dict:
    """FastAPI dependency — geeft de server configuraties uit app.state."""
    configs: dict = request.app.state.server_configs
    return configs


# ─── Helpers ───────────────────────────────────────────────────────

async def _get_agent_data(manager: AgentManager, agent_id: str) -> dict:
    """Haal overview data op van een agent, met foutafhandeling."""
    client = manager.get_client(agent_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail={"error": "agent_not_found", "message": f"Agent '{agent_id}' niet gevonden"},
        )

    data = await client.get_overview()
    if data is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "agent_unavailable", "message": f"Agent '{agent_id}' is niet bereikbaar"},
        )

    return data


# ─── Endpoints ─────────────────────────────────────────────────────

@router.get("/servers", summary="Lijst van geconfigureerde servers")
async def list_servers(
    manager: AgentManager = Depends(get_manager),
    configs: dict = Depends(get_server_configs),
) -> list[dict]:
    """Geeft een lijst van alle geconfigureerde server-agents."""
    servers_list: list[dict] = []
    for sid, cfg in configs.items():
        client = manager.get_client(sid)
        online = await client.health_check() if client else False
        servers_list.append({
            "id": sid,
            "name": cfg.get("name", sid),
            "url": cfg.get("url", ""),
            "online": online,
        })
    return servers_list


@router.get("/servers/{server_id}/overview", response_model=AgentOverview)
async def get_server_overview(
    server_id: str,
    manager: AgentManager = Depends(get_manager),
) -> AgentOverview:
    """Haal alle data van één server-agent op."""
    data = await _get_agent_data(manager, server_id)
    return AgentOverview(**data)


@router.get("/servers/{server_id}/os", response_model=OSInfo)
async def get_server_os(
    server_id: str,
    manager: AgentManager = Depends(get_manager),
) -> OSInfo:
    """Haal OS-info van een server-agent op."""
    data = await _get_agent_data(manager, server_id)
    return OSInfo(**data["os"])


@router.get("/servers/{server_id}/hardware", response_model=HardwareMetrics)
async def get_server_hardware(
    server_id: str,
    manager: AgentManager = Depends(get_manager),
) -> HardwareMetrics:
    """Haal hardware metrics van een server-agent op."""
    data = await _get_agent_data(manager, server_id)
    return HardwareMetrics(**data["hardware"])


@router.get("/servers/{server_id}/storage", response_model=list[StorageInfo])
async def get_server_storage(
    server_id: str,
    manager: AgentManager = Depends(get_manager),
) -> list[StorageInfo]:
    """Haal opslaginformatie van een server-agent op."""
    data = await _get_agent_data(manager, server_id)
    return [StorageInfo(**s) for s in data["storage"]]


@router.get("/servers/{server_id}/containers", response_model=list[ContainerInfo])
async def get_server_containers(
    server_id: str,
    manager: AgentManager = Depends(get_manager),
) -> list[ContainerInfo]:
    """Haal Docker container lijst van een server-agent op."""
    data = await _get_agent_data(manager, server_id)
    return [ContainerInfo(**c) for c in data["containers"]]


@router.post("/servers/{server_id}/containers/{container_id}/{action}")
async def perform_container_action(
    server_id: str,
    container_id: str,
    action: str,
    manager: AgentManager = Depends(get_manager),
) -> dict:
    """Voer een actie uit op een container via de server-agent."""
    if action not in ("start", "stop", "restart"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_action",
                "message": f"Ongeldige actie '{action}'. Gebruik: start, stop, restart",
            },
        )

    client = manager.get_client(server_id)
    if not client:
        raise HTTPException(
            status_code=404,
            detail={"error": "agent_not_found", "message": f"Agent '{server_id}' niet gevonden"},
        )

    result = await client.container_action(container_id, action)

    if result is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "agent_unavailable", "message": f"Agent '{server_id}' is niet bereikbaar"},
        )

    if not result.get("success", False):
        detail = result.get("message", "Onbekende fout")
        status = 503 if "niet beschikbaar" in detail else 500
        if "niet gevonden" in detail:
            status = 404
        raise HTTPException(status_code=status, detail=result)

    return result


@router.get("/dashboard", summary="Volledige dashboard data (alle servers)")
async def get_dashboard(
    manager: AgentManager = Depends(get_manager),
    configs: dict = Depends(get_server_configs),
) -> dict:
    """Haal data van alle servers gelijktijdig op voor het dashboard."""
    results = await manager.collect_all()

    dashboard_data: dict = {}
    for server_id in configs:
        data = results.get(server_id)
        if data:
            try:
                dashboard_data[server_id] = AgentOverview(**data).model_dump()
            except Exception as e:
                logger.error("Fout bij parsen data voor %s: %s", server_id, e)
                dashboard_data[server_id] = None
        else:
            dashboard_data[server_id] = None

    return {
        "servers": dashboard_data,
        "config": {
            sid: {"name": cfg.get("name", sid)}
            for sid, cfg in configs.items()
        },
    }
