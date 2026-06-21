"""API endpoints per server — haalt data op van de agents."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from ..config import AGENTS
from ..models.schemas import ServerOverview
from ..services.agent_client import AgentClient
from .auth import verify_api_key

router = APIRouter(prefix="/api/servers", tags=["Servers"])


def _get_agent(server_id: str) -> AgentClient:
    """Kort helper om een AgentClient te maken voor een server-ID."""
    if server_id not in AGENTS:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' niet gevonden",
        )
    return AgentClient(server_id)


@router.get("/")
async def list_servers(
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Lijst alle gekende servers op."""
    return {
        "servers": [
            {"id": sid, "name": cfg["name"], "url": cfg["url"]}
            for sid, cfg in AGENTS.items()
        ]
    }


@router.get("/{server_id}/overview")
async def get_server_overview(
    server_id: str,
    _: str = Depends(verify_api_key),
) -> ServerOverview:
    """Volledig overzicht van één server (OS + storage + hardware + docker)."""
    agent = _get_agent(server_id)
    data = await agent.get_overview()
    return ServerOverview(**data)


@router.get("/{server_id}/os")
async def get_server_os(
    server_id: str,
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """OS-info van een server."""
    agent = _get_agent(server_id)
    return await agent.get_os_info()


@router.get("/{server_id}/storage")
async def get_server_storage(
    server_id: str,
    _: str = Depends(verify_api_key),
) -> Any:
    """Opslag-info van een server."""
    agent = _get_agent(server_id)
    return await agent.get_storage()


@router.get("/{server_id}/hardware")
async def get_server_hardware(
    server_id: str,
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """CPU/RAM-metrics van een server."""
    agent = _get_agent(server_id)
    return await agent.get_hardware()
