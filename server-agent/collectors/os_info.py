"""Verzamelt OS-info: hostname, OS-type, kernel, uptime."""

from __future__ import annotations

import platform
import time
from pathlib import Path

import psutil

from . import OSType


def collect() -> dict:
    """Geeft hostname, os_type, kernel_version en uptime terug."""
    hostname = platform.node()
    os_type = _detect_os_type()
    kernel = platform.release()
    uptime = _get_uptime()

    return {
        "hostname": hostname,
        "os_type": os_type.value,
        "kernel_version": kernel,
        "uptime": uptime,
    }


def _detect_os_type() -> OSType:
    """Detecteer het OS-type (UmbrelOS, Ubuntu, Windows, ...)."""
    # Eerst platform.check
    system = platform.system()
    if system == "Windows":
        return OSType.WINDOWS

    # Linux-specifieke detectie
    # UmbrelOS heeft typisch een /umbrel-root of /umbrel map
    if Path("/umbrel").exists() or Path("/umbrel-root").exists():
        return OSType.UMBRELOS
    # Check /etc/os-release voor Ubuntu
    os_release = Path("/etc/os-release")
    if os_release.exists():
        content = os_release.read_text()
        if "Ubuntu" in content:
            return OSType.UBUNTU
    return OSType.UNKNOWN


def _get_uptime() -> str:
    """Bereken uptime via psutil (cross-platform)."""
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)
    except Exception:
        return "onbekend"
