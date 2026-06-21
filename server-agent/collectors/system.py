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


def collect_storage() -> list:
    """Geeft schijfruimte van alle fysieke schijven."""
    storages = []
    for part in psutil.disk_partitions():
        # Sla pseudo/virtuele bestandssystemen over
        if part.fstype in (
            "proc", "sysfs", "devtmpfs", "tmpfs", "devpts",
            "fusectl", "cgroup", "cgroup2", "pstore",
            "securityfs", "selinuxfs", "autofs", "mqueue",
            "hugetlbfs", "configfs", "debugfs", "tracefs",
            "ramfs", "overlay", "overlay2",
        ):
            continue
        # Sla loop-apparaten over
        if part.device and "loop" in part.device:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            storages.append({
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "available_gb": round(usage.free / (1024**3), 2),
                "used_percent": usage.percent,
                "mount_point": part.mountpoint,
                "device": part.device or "",
                "fstype": part.fstype,
            })
        except PermissionError:
            continue
    return storages
