"""Verzamelt OS-info: hostname, OS-type, kernel, uptime.

Werkt zowel native (Ubuntu Server) als in Docker (UmbrelOS).
In Docker-modus wordt /host/ gebruikt voor hostname en OS-detectie.
"""

from __future__ import annotations

import logging
import platform
import time
from pathlib import Path

import psutil

from . import OSType, format_uptime

logger = logging.getLogger(__name__)

# Paden voor hostname detectie (in volgorde van betrouwbaarheid)
_HOSTNAME_PATHS: list[Path] = [
    Path("/host/proc/sys/kernel/hostname"),  # Beste: host kernel via Docker mount
    Path("/host/etc/hostname"),              # Host /etc/hostname via Docker mount
    Path("/etc/hostname"),                   # Fallback: container eigen hostname
]

# Paden voor OS-release detectie (in volgorde van betrouwbaarheid)
_OS_RELEASE_PATHS: list[Path] = [
    Path("/host/etc/os-release"),
    Path("/etc/os-release"),
    Path("/host/etc/lsb-release"),
    Path("/etc/lsb-release"),
]

# UmbrelOS marker bestanden
_UMBREL_MARKERS: list[Path] = [
    Path("/umbrel"),
    Path("/umbrel-root"),
]


def _is_containerized() -> bool:
    """Detecteer of we in een Docker container draaien."""
    return Path("/.dockerenv").exists()


def _looks_like_container_id(hostname: str) -> bool:
    """Controleer of een hostname een Docker container-ID lijkt.

    Docker korte IDs zijn exact 12 hex chars, lange IDs 64 hex chars.
    """
    if not hostname or not hostname.isascii():
        return False
    hex_chars = set("0123456789abcdefABCDEF")
    if not all(c in hex_chars for c in hostname):
        return False
    return len(hostname) in (12, 64)


def _get_host_hostname() -> str:
    """Lees de hostname, met fallback-hiërarchie voor Docker.

    Probeert:
    1. /host/proc/sys/kernel/hostname (host gemount in Docker)
    2. /host/etc/hostname
    3. /etc/hostname (container eigen hostname)
    4. platform.node() (ultimate fallback)
    """
    # Check of we in Docker zitten maar /host/ niet gemount is
    if _is_containerized() and not Path("/host/proc/sys/kernel/hostname").exists():
        logger.warning(
            "Draaiend in Docker maar /host/ volume niet gemount. "
            "Hostname kan het container-ID zijn. Mount host /proc voor correcte hostname."
        )

    for path in _HOSTNAME_PATHS:
        try:
            if path.exists():
                value = path.read_text().strip()
                if value:
                    return value
        except (PermissionError, OSError) as e:
            logger.debug("Kan %s niet lezen: %s", path, e)
            continue

    # Fallback — platform.node() geeft in Docker vaak het container-ID
    node = platform.node()
    if _looks_like_container_id(node):
        logger.warning(
            "Hostname '%s' lijkt op een container-ID (lengte %d). "
            "Mount /proc van de host naar /host/proc voor de juiste hostnaam.",
            node,
            len(node),
        )
    return node


def _detect_os_type() -> OSType:
    """Detecteer het OS-type van de host.

    Detectie volgorde:
    1. Windows check (platform.system())
    2. UmbrelOS markers checken (/umbrel, /umbrel-root)
    3. OS-release bestanden lezen
    4. Fallback naar UNKNOWN
    """
    if platform.system() == "Windows":
        return OSType.WINDOWS

    # UmbrelOS detectie — markers bestaan
    for marker in _UMBREL_MARKERS:
        if marker.exists():
            logger.info("UmbrelOS gedetecteerd via marker: %s", marker)
            return OSType.UMBRELOS

    # OS-release bestanden lezen
    for path in _OS_RELEASE_PATHS:
        try:
            if path.exists():
                content = path.read_text().lower()
                if "ubuntu" in content:
                    return OSType.UBUNTU
                if "umbrel" in content or "umbrelos" in content:
                    return OSType.UMBRELOS
        except (PermissionError, OSError) as e:
            logger.debug("Kan %s niet lezen: %s", path, e)
            continue

    logger.warning("OS-type niet gedetecteerd uit release bestanden — valt terug naar UNKNOWN")
    return OSType.UNKNOWN


def _get_uptime() -> str:
    """Bereken uptime via psutil en geef leesbare string terug."""
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        return format_uptime(uptime_seconds)
    except Exception as e:
        logger.error("Fout bij berekenen uptime: %s", e)
        return "onbekend"


def collect() -> dict:
    """Verzamel alle OS-info.

    Returns:
        dict met hostname, os_type, kernel_version, uptime
    """
    hostname = _get_host_hostname()
    os_type_value = _detect_os_type()
    kernel = platform.release()
    uptime = _get_uptime()

    logger.info(
        "OS collect: hostname=%s, os_type=%s, kernel=%s, uptime=%s",
        hostname,
        os_type_value.value,
        kernel,
        uptime,
    )

    return {
        "hostname": hostname,
        "os_type": os_type_value.value,
        "kernel_version": kernel,
        "uptime": uptime,
    }
