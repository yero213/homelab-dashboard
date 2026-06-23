"""Pydantic modellen voor Homelab Dashboard.

Definieert de datastructuren voor communicatie tussen
dashboard en server-agents, plus frontend data types.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ─── Agent data modellen ───────────────────────────────────────────

class OSInfo(BaseModel):
    """Besturingssysteem informatie van een server-agent."""
    hostname: str = Field(..., description="Hostnaam van de server")
    os_type: str = Field(..., description="Type besturingssysteem (umbrelos, ubuntu, windows, unknown)")
    kernel_version: str = Field(..., description="Kernel versie")
    uptime: str = Field(..., description="Leesbare uptime string")


class HardwareMetrics(BaseModel):
    """Hardware metrics (CPU, RAM) van een server-agent."""
    cpu_percent: float = Field(..., description="CPU gebruik (0-100%, kan >100 op multi-core)")
    cpu_cores: int = Field(..., description="Aantal CPU cores (inclusief hyperthreading)")
    ram_total_gb: float = Field(..., description="Totaal RAM in GB")
    ram_used_gb: float = Field(..., description="Gebruikt RAM in GB")
    ram_percent: float = Field(..., description="RAM gebruik percentage")


class StorageInfo(BaseModel):
    """Opslaginformatie van een schijf."""
    total_gb: float = Field(..., description="Totale grootte in GB")
    used_gb: float = Field(..., description="Gebruikte ruimte in GB")
    available_gb: float = Field(..., description="Beschikbare ruimte in GB")
    used_percent: float = Field(..., description="Gebruikspercentage")
    mount_point: str = Field(..., description="Mountpoint (bv. /, /data)")
    device: str = Field(..., description="Device pad (bv. /dev/nvme0n1p1)")
    fstype: str = Field(..., description="Filesystem type (bv. ext4, btrfs)")


class ContainerInfo(BaseModel):
    """Docker container informatie."""
    id: str = Field(..., description="Kort container-ID (12 chars)")
    name: str = Field(..., description="Container naam")
    image: str = Field(..., description="Docker image naam")
    status: str = Field(..., description="Status: running, stopped, paused, etc.")
    health_status: Optional[str] = Field(None, description="Healthcheck status (healthy, unhealthy)")
    uptime: Optional[str] = Field(None, description="Container uptime")
    ports: str = Field("", description="Port mapping string (bv. '8080→80/tcp')")


class ContainerActionResult(BaseModel):
    """Resultaat van een container actie (start/stop/restart)."""
    success: bool = Field(..., description="Of de actie is gelukt")
    message: str = Field(..., description="Beschrijving van het resultaat")


class AgentOverview(BaseModel):
    """Gecombineerde data van één server-agent."""
    os: OSInfo
    hardware: HardwareMetrics
    storage: list[StorageInfo]
    containers: list[ContainerInfo]


# ─── Dashboard configuratie ────────────────────────────────────────

class ServerConfig(BaseModel):
    """Configuratie voor één server/agent."""
    id: str = Field(..., description="Unieke identifier (bv. 'umbrelos', 'ubuntu')")
    name: str = Field(..., description="Leesbare naam (bv. 'UmbrelOS', 'Ubuntu Server')")
    url: str = Field(..., description="Basis-URL van de agent")
    api_key: str = Field(..., description="API-key voor authenticatie")


class DashboardStatus(BaseModel):
    """Status van het dashboard — verzamelde data van alle servers."""
    servers: list[ServerConfig] = Field(default_factory=list)
    last_updated: Optional[str] = None
    errors: dict[str, str] = Field(default_factory=dict)
