"""Verzamelt OS-info: hostname, OS-type, kernel, uptime."""

from __future__ import annotations

import logging
import platform
import time
from pathlib import Path

import psutil

from . import OSType

logger = logging.getLogger(__name__)


def _get_host_hostname() -> str:
    """Lees de hostname van de host uit (werkt ook in Docker).

    Probeer volgende methodes in volgorde:
    1. /host/proc/sys/kernel/hostname (host gemount via Docker)
    2. /host/etc/hostname (host filesystem gemount)
    3. /etc/hostname (container eigen hostname — beter dan container-ID)
    4. platform.node() (fallback)
    """
    candidates = [
        Path("/host/proc/sys/kernel/hostname"),
        Path("/host/etc/hostname"),
        Path("/etc/hostname"),
    ]
    for path in candidates:
        try:
            if path.exists():
                value = path.read_text().strip()
                if value:
                    return value
        except (PermissionError, OSError):
            continue

    # Fallback — platform.node() geeft in Docker vaak het container-ID
    node = platform.node()
    # Als het eruit ziet als een container-ID (lang hex string), noteer een warning
    if len(node) > 12 and all(c in "0123456789abcdef" for c in node.lower()):
        logger.warning(
            "Hostname lijkt op een container-ID (%s). "
            "Mount /proc van de host naar /host/proc in de container voor de juiste hostnaam.",
            node,
        )
    return node


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
