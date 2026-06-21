"""API endpoints voor Docker-beheer via de agents."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from ..config import AGENTS
from ..models.schemas import ContainerActionRequest, DockerContainer
from ..services.agent_client import AgentClient
from .auth import verify_api_key

router = APIRouter(prefix="/api/servers/{server_id}/docker", tags=["Docker"])


def _get_agent(server_id: str) -> AgentClient:
    if server_id not in AGENTS:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' niet gevonden",
        )
    return AgentClient(server_id)


@router.get("/")
async def list_containers(
    server_id: str,
    _: str = Depends(verify_api_key),
) -> List[DockerContainer]:
    """Lijst alle Docker-containers op een server."""
    agent = _get_agent(server_id)
    data = await agent.get_docker_containers()
    return [DockerContainer(**c) for c in data.get("containers", [])]


@router.post("/{container_id}/{action}")
async def container_action(
    server_id: str,
    container_id: str,
    action: str,
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    """Start / stop / herstart een container.

    Geldige acties: start, stop, restart
    """
    valid_actions = {"start", "stop", "restart"}
    if action not in valid_actions:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ongeldige actie '{action}'. Kies uit: {', '.join(valid_actions)}",
        )

    agent = _get_agent(server_id)
    return await agent.container_action(container_id, action)
