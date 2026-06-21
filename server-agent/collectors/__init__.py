"""Collectors package — bevat alle dataverzamelaars voor de agent."""

from __future__ import annotations

from enum import Enum


class OSType(Enum):
    UMBRELOS = "umbrelos"
    UBUNTU = "ubuntu"
    WINDOWS = "windows"
    UNKNOWN = "unknown"
