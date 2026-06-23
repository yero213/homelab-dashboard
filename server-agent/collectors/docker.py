"""Verzamelt Docker-container info en voert acties uit.

Gebruikt de Docker SDK voor Python (docker-py).
Containerstatussen worden vertaald van Docker-formaat naar frontend-formaat.
Als Docker niet beschikbaar is (geen socket, niet geïnstalleerd),
wordt graceful een lege lijst teruggegeven.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import docker
from docker.errors import DockerException, NotFound, APIError

logger = logging.getLogger(__name__)

# Docker-status → frontend-status mapping
STATUS_MAP: dict[str, str] = {
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
    """Maak een Docker-client aan.

    Geeft None terug als Docker niet beschikbaar is (geen fout).
    """
    try:
        return docker.from_env()
    except DockerException as e:
        logger.warning("Docker niet beschikbaar: %s", e)
        return None


def _get_image_name(container) -> str:
    """Haal de image-naam op van een container.

    Als er geen tags zijn, val terug op het image-ID.
    """
    try:
        if container.image.tags:
            return container.image.tags[0]
        return f"<image:{container.image.short_id}>"
    except Exception:
        return "unknown"


def _calculate_uptime(container) -> Optional[str]:
    """Bereken de uptime van een container op basis van StartedAt.

    Returns:
        leesbare uptime string (bv. '2h 30m 15s') of None
    """
    try:
        started_at_str = container.attrs.get("State", {}).get("StartedAt")
        if not started_at_str:
            return None

        # Parse ISO8601 timestamp (verwijder 'Z' en microseconden voor compatibiliteit)
        started_at_str = started_at_str.replace("Z", "+00:00")
        # Splits op microseconden als die er zijn
        if "." in started_at_str:
            started_at_str = started_at_str.split(".")[0] + "+00:00"

        started_at = datetime.fromisoformat(started_at_str)
        uptime_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()

        if uptime_seconds < 0:
            return None

        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        secs = int(uptime_seconds % 60)

        parts: list[str] = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or (days == 0 and hours == 0):
            parts.append(f"{minutes}m")
        if days == 0 and hours == 0 and minutes < 1:
            parts.append(f"{secs}s")

        return " ".join(parts)
    except Exception as e:
        logger.debug("Fout bij berekenen container uptime: %s", e)
        return None


def _format_ports(ports_dict: Optional[dict]) -> str:
    """Maak een leesbare string van de port mapping.

    Voorbeeld: '8080→80/tcp, 443→443/tcp'
    """
    if not ports_dict:
        return ""

    parts: list[str] = []
    for container_port, bindings in ports_dict.items():
        if bindings:
            for b in bindings:
                host_port = b.get("HostPort", "?")
                parts.append(f"{host_port}→{container_port}")
        else:
            parts.append(container_port)
    return ", ".join(parts)


def _get_health_status(container) -> Optional[str]:
    """Lees de health status van een container."""
    try:
        return container.attrs.get("State", {}).get("Health", {}).get("Status")
    except Exception:
        return None


def list_containers() -> list[dict]:
    """Geeft een lijst van alle containers (actief + gestopt).

    Returns:
        lijst van dicts met container-informatie
    """
    client = _get_client()
    if client is None:
        return []

    containers: list[dict] = []
    try:
        for c in client.containers.list(all=True):
            docker_status = c.status or "unknown"
            health = _get_health_status(c)

            containers.append({
                "id": c.short_id,
                "name": c.name,
                "image": _get_image_name(c),
                "status": STATUS_MAP.get(docker_status, "unknown"),
                "health_status": health,
                "uptime": _calculate_uptime(c),
                "ports": _format_ports(
                    c.attrs.get("NetworkSettings", {}).get("Ports", {})
                ),
            })
    except DockerException as e:
        logger.error("Fout bij ophalen containers: %s", e)

    return containers


def container_action(container_id: str, action: str) -> dict:
    """Voer een actie uit op een container (start/stop/restart).

    Args:
        container_id: korte of lange container-ID
        action: "start", "stop", of "restart"

    Returns:
        dict met success (bool) en message (str)
    """
    client = _get_client()
    if client is None:
        return {"success": False, "message": "Docker niet beschikbaar"}

    try:
        container = client.containers.get(container_id)
    except NotFound:
        logger.error("Container niet gevonden: %s", container_id)
        return {"success": False, "message": f"Container '{container_id}' niet gevonden"}
    except DockerException as e:
        logger.error("Docker fout bij ophalen container %s: %s", container_id, e)
        return {"success": False, "message": f"Docker fout: {e}"}

    try:
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop()
        elif action == "restart":
            container.restart()
        else:
            return {"success": False, "message": f"Ongeldige actie: {action}"}

        logger.info("Container %s %s uitgevoerd", container_id, action)
        return {"success": True, "message": f"Container {action} uitgevoerd"}

    except APIError as e:
        logger.error("API fout bij %s container %s: %s", action, container_id, e)
        return {"success": False, "message": f"Fout bij {action}: {e.explanation or e}"}
