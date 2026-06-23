"""Collectors package — dataverzamelaars voor de server-agent.

Elke collector haalt specifieke systeeminformatie op van de host:
- os_info: hostname, OS-type, kernel, uptime
- system:  CPU, RAM, opslag
- docker:  Docker containers en acties
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class OSType(str, Enum):
    """Ondersteunde besturingssystemen voor het homelab dashboard."""

    UMBRELOS = "umbrelos"
    UBUNTU = "ubuntu"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


def format_uptime(seconds: float) -> str:
    """Zet een aantal seconden om in een leesbare uptime string (bv. '3d 12h 5m')."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    parts: list[str] = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)
