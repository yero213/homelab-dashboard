"""HTTPX client voor communicatie met server-agents.

Verzorgt het ophalen van data van elke server-agent via zijn REST API,
inclusief X-API-Key authenticatie, timeout handling, en error afhandeling.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── Standaard timeout configuratie ─────────────────────────────────
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)  # 10s totaal, 5s connect
_MAX_RETRIES = 2


class AgentClient:
    """Client voor communicatie met één server-agent.

    Voorziet elke request van de juiste X-API-Key header.
    Gebruikt connection pooling voor efficiëntie bij meerdere requests.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        """Initialiseer client voor een specifieke agent.

        Args:
            base_url: Basis-URL van de agent (bv. http://192.168.1.100:9100)
            api_key: API-key voor authenticatie
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        # Connection pool met limiet voor homelab gebruik
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
        )
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-API-Key": self.api_key},
            timeout=_TIMEOUT,
            limits=limits,
        )

    async def _request(self, method: str, path: str) -> dict | list | None:
        """Interne methode voor het uitvoeren van een HTTP request.

        Args:
            method: HTTP methode (GET, POST)
            path: API pad (bv. /os, /hardware)

        Returns:
            JSON response als dict of list, of None bij fout
        """
        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.request(method, path)

                if response.status_code == 200:
                    return response.json()

                if response.status_code in (401, 403):
                    logger.error(
                        "Authenticatie fout voor %s%s: status=%d",
                        self.base_url, path, response.status_code,
                    )
                    return None

                if response.status_code == 503:
                    logger.warning("Agent %s niet beschikbaar (%s)", self.base_url, path)
                    return None

                # Andere fouten — log en retry
                logger.warning(
                    "Onverwachte status %d van %s%s (poging %d/%d)",
                    response.status_code, self.base_url, path,
                    attempt + 1, _MAX_RETRIES,
                )

                if attempt < _MAX_RETRIES - 1:
                    continue

                return None

            except httpx.TimeoutException:
                logger.warning(
                    "Timeout voor %s%s (poging %d/%d)",
                    self.base_url, path, attempt + 1, _MAX_RETRIES,
                )
                if attempt < _MAX_RETRIES - 1:
                    continue
                return None

            except httpx.RequestError as e:
                logger.error(
                    "Verbindingsfout voor %s%s: %s",
                    self.base_url, path, e,
                )
                return None

        return None

    async def get_os(self) -> dict | None:
        """Haal OS-info op van de agent."""
        result = await self._request("GET", "/os")
        return result if isinstance(result, dict) else None

    async def get_hardware(self) -> dict | None:
        """Haal hardware metrics op van de agent."""
        result = await self._request("GET", "/hardware")
        return result if isinstance(result, dict) else None

    async def get_storage(self) -> list | None:
        """Haal opslaginformatie op van de agent."""
        result = await self._request("GET", "/storage")
        return result if isinstance(result, list) else None

    async def get_containers(self) -> list | None:
        """Haal Docker container lijst op van de agent."""
        result = await self._request("GET", "/containers")
        return result if isinstance(result, list) else None

    async def get_overview(self) -> dict | None:
        """Haal alle metrics in één request op (via /overview)."""
        result = await self._request("GET", "/overview")
        return result if isinstance(result, dict) else None

    async def container_action(self, container_id: str, action: str) -> dict | None:
        """Voer een actie uit op een container (start/stop/restart).

        Args:
            container_id: Container-ID
            action: start, stop, of restart

        Returns:
            Response dict met success en message
        """
        result = await self._request("POST", f"/containers/{container_id}/{action}")
        return result if isinstance(result, dict) else None

    async def health_check(self) -> bool:
        """Controleer of de agent bereikbaar is.

        Returns:
            True als de agent /health met status 200 beantwoordt
        """
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except httpx.RequestError:
            return False

    async def close(self) -> None:
        """Sluit de HTTPX client (geef resources vrij)."""
        await self._client.aclose()


# ─── Manager voor meerdere agents ──────────────────────────────────

class AgentManager:
    """Beheert meerdere AgentClient instanties.

    Voorziet in het gelijktijdig ophalen van data van alle agents.
    """

    def __init__(self, agents: dict[str, tuple[str, str]] | None = None) -> None:
        """Initialiseer met optionele agent configuratie.

        Args:
            agents: Dict met {id: (base_url, api_key)}
        """
        self._clients: dict[str, AgentClient] = {}
        if agents:
            for agent_id, (url, key) in agents.items():
                self._clients[agent_id] = AgentClient(url, key)

    def add_agent(self, agent_id: str, base_url: str, api_key: str) -> None:
        """Voeg een agent toe aan de manager."""
        self._clients[agent_id] = AgentClient(base_url, api_key)

    def get_client(self, agent_id: str) -> AgentClient | None:
        """Haal een AgentClient op via ID."""
        return self._clients.get(agent_id)

    @property
    def agent_ids(self) -> list[str]:
        """Lijst van alle geregistreerde agent IDs."""
        return list(self._clients.keys())

    async def collect_all(self) -> dict[str, dict | None]:
        """Haal gelijktijdig overview op van alle agents.

        Returns:
            Dict met {agent_id: overview_data or None}
        """
        import asyncio

        async def fetch(agent_id: str, client: AgentClient) -> tuple[str, dict | None]:
            data = await client.get_overview()
            return agent_id, data

        tasks = [
            fetch(aid, client)
            for aid, client in self._clients.items()
        ]

        results = {}
        for task in asyncio.as_completed(tasks):
            agent_id, data = await task
            results[agent_id] = data

        return results

    async def close_all(self) -> None:
        """Sluit alle agent clients."""
        for client in self._clients.values():
            await client.close()
