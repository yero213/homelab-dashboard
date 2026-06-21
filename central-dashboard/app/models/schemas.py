"""Pydantic modellen voor API request/response data."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ─── Enums ───────────────────────────────────────────────────────────
class OSType(str, Enum):
    UMBRELOS = "umbrelos"
    UBUNTU = "ubuntu"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


class ContainerStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    CREATED = "created"
    RESTARTING = "restarting"
    REMOVING = "removing"
    DEAD = "dead"
    UNKNOWN = "unknown"


# ─── Agent response modellen ─────────────────────────────────────────
class OSInfo(BaseModel):
    hostname: str
    os_type: OSType
    kernel_version: str
    uptime: str


class StorageInfo(BaseModel):
    total_gb: float
    used_gb: float
    available_gb: float
    used_percent: float
    mount_point: str
    device: Optional[str] = None
    fstype: Optional[str] = None


class HardwareMetrics(BaseModel):
    cpu_percent: float
    cpu_cores: int
    ram_total_gb: float
    ram_used_gb: float
    ram_percent: float


class DockerContainer(BaseModel):
    id: str
    name: str
    image: str
    status: ContainerStatus
    uptime: Optional[str] = None
    ports: Optional[str] = None


class ServerOverview(BaseModel):
    os: OSInfo
    storage: List[StorageInfo]
    hardware: HardwareMetrics
    docker_containers: List[DockerContainer]


# ─── Actie requests ──────────────────────────────────────────────────
class ContainerActionRequest(BaseModel):
    container_id: str
    action: str  # start | stop | restart
