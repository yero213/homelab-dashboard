"""HTTP client om met de server-agents te communiceren.

Elke agent exposeert een REST API op z'n eigen poort.
Dit竟是 de centrale plek waar we die calls doen.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from ..config import AGENTS

logger = logging.getLogger(__name__)


class AgentClient:
    """Praat met één specifieke server-agent."""

    def __init__(self, agent_id: str) -> None:
        if agent_id not in AGENTS:
            raise ValueError(f"Onbekende agent: {agent_id}")
        cfg = AGENTS[agent_id]
        self.base_url = cfg["url"].rstrip("/")
        self.api_key = cfg["api_key"]
        self.timeout = httpx.Timeout(10.0)

    async def _get(self, path: str) -> Dict[str, Any]:
        """Interne helper: GET-request met API-key."""
        url = f"{self.base_url}{path}"
        headers = {"X-API-Key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Agent HTTP %s: %s", e.response.status_code, url)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Agent fout: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error("Agent onbereikbaar: %s — %s", url, e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Agent onbereikbaar: {e}",
            )

    async def _post(
        self, path: str, body: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Interne helper: POST-request met API-key."""
        url = f"{self.base_url}{path}"
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=body or {})
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Agent HTTP %s: %s", e.response.status_code, url)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Agent fout: {e.response.text}",
            )
        except httpx.RequestError as e:
            logger.error("Agent onbereikbaar: %s — %s", url, e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Agent onbereikbaar: {e}",
            )

    # ─── Publieke API's ──────────────────────────────────────────

    async def get_overview(self) -> Dict[str, Any]:
        """Haal alle data in één request op (OS + storage + hardware + docker)."""
        return await self._get("/overview")

    async def get_os_info(self) -> Dict[str, Any]:
        return await self._get("/os")

    async def get_storage(self) -> Dict[str, Any]:
        return await self._get("/storage")

    async def get_hardware(self) -> Dict[str, Any]:
        return await self._get("/hardware")

    async def get_docker_containers(self) -> Dict[str, Any]:
        return await self._get("/docker")

    async def container_action(
        self, container_id: str, action: str
    ) -> Dict[str, Any]:
        return await self._post(
            f"/docker/{container_id}/{action}",
        )
