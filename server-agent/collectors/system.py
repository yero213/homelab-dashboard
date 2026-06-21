"""Verzamelt hardware metrics (CPU, RAM) en opslag-info.

Gebruikt psutil voor cross-platform compatibiliteit.
"""

from __future__ import annotations

import psutil


def collect_hardware() -> dict:
    """Geeft CPU-percentage, cores, RAM-totaal/gebruik/procent."""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_cores = psutil.cpu_count(logical=True)
    ram = psutil.virtual_memory()

    return {
        "cpu_percent": cpu_percent,
        "cpu_cores": cpu_cores,
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "ram_percent": ram.percent,
    }


def collect_storage() -> dict:
    """Geeft schijfruimte van de root-partitie."""
    usage = psutil.disk_usage("/")
    return {
        "total_gb": round(usage.total / (1024**3), 2),
        "used_gb": round(usage.used / (1024**3), 2),
        "available_gb": round(usage.free / (1024**3), 2),
        "used_percent": usage.percent,
        "mount_point": "/",
    }
