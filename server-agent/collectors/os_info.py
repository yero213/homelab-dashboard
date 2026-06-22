"""Verzamelt OS-info: hostname, OS-type, kernel, uptime."""

from __future__ import annotations

import platform
import time
from pathlib import Path

import psutil

from . import OSType


def _get_host_hostname() -> str:
    """Lees de hostname van de host uit (werkt ook in Docker)."""
    hostname_path = Path("/host/proc/sys/kernel/hostname")
    if hostname_path.exists():
        return hostname_path.read_text().strip()
    return platform.node()


def collect() -> dict:
    """Geeft hostname, os_type, kernel_version en uptime terug."""
    hostname = _get_host_hostname()
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
    """Detecteer het OS-type op basis van de host (via gemounte paden)."""
    system = platform.system()
    if system == "Windows":
        return OSType.WINDOWS

    # Controleer of dit een UmbrelOS-host is (via gemounte /host/etc of /umbrel)
    if Path("/umbrel").exists() or Path("/umbrel-root").exists():
        return OSType.UMBRELOS

    # Lees /etc/os-release van de host (via gemounte /host/etc)
    for os_release_path in [Path("/host/etc/os-release"), Path("/etc/os-release")]:
        if os_release_path.exists():
            content = os_release_path.read_text().lower()
            if "ubuntu" in content:
                return OSType.UBUNTU
            break

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
