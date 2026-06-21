"""Verzamelt Docker-container info en voert acties uit.

Gebruikt de Docker SDK voor Python (docker-py).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)

# Docker-status → frontend-status mapping
STATUS_MAP = {
    "running": "running",
    "exited": "stopped",
    "stopped": "stopped",
    "paused": "paused",
    "created": "created",
    "restarting": "restarting",
    "removing": "removing",
    "dead": "dead",
}


def _get_client() -> Optional[docker.DockerClient]:
    """Maak een Docker-client aan. Geeft None als Docker niet beschikbaar is."""
    try:
        return docker.from_env()
    except DockerException as e:
        logger.warning("Docker niet beschikbaar: %s", e)
        return None


def list_containers() -> List[Dict[str, Any]]:
    """Geeft een lijst van alle containers (actief + gestopt)."""
    client = _get_client()
    if client is None:
        return []

    containers = []
    try:
        for c in client.containers.list(all=True):
            docker_status = c.status
            containers.append(
                {
                    "id": c.short_id,
                    "name": c.name,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                    "status": STATUS_MAP.get(docker_status, "unknown"),
                    "uptime": c.attrs.get("State", {}).get("StartedAt", ""),
                    "ports": _format_ports(c.attrs.get("NetworkSettings", {}).get("Ports", {})),
                }
            )
    except DockerException as e:
        logger.error("Fout bij ophalen containers: %s", e)

    return containers


def container_action(container_id: str, action: str) -> Dict[str, Any]:
    """Voer een actie uit op een container (start/stop/restart)."""
    client = _get_client()
    if client is None:
        return {"success": False, "message": "Docker niet beschikbaar"}

    try:
        container = client.containers.get(container_id)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop()
        elif action == "restart":
            container.restart()
        else:
            return {"success": False, "message": f"Ongeldige actie: {action}"}

        return {"success": True, "message": f"Container {action} uitgevoerd"}
    except DockerException as e:
        logger.error("Fout bij %s container %s: %s", action, container_id, e)
        return {"success": False, "message": str(e)}


def _format_ports(ports_dict: Optional[dict]) -> str:
    """Maak een leesbare string van de port mapping."""
    if not ports_dict:
        return ""
    parts = []
    for container_port, bindings in ports_dict.items():
        if bindings:
            for b in bindings:
                host_port = b.get("HostPort", "?")
                parts.append(f"{host_port}→{container_port}")
        else:
            parts.append(container_port)
    return ", ".join(parts)
