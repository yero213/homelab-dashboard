"""Verzamelt hardware metrics (CPU, RAM) en opslag-info.

Gebruikt psutil voor cross-platform compatibiliteit.
In Docker worden host-schijven gelezen via /host/ als die gemount zijn.
Ondersteunt LVM, RAID, Btrfs, ZFS en andere fysieke schijven.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# ─── Cache voor /proc/mounts ────────────────────────────────────────
_MOUNT_CACHE: dict[str, Any] = {"data": None, "timestamp": 0.0}
_MOUNT_CACHE_TTL = 5.0  # seconden

# ─── Filesystem types die we overslaan (pseudo/virtueel) ────────────
PSEUDO_FS: frozenset[str] = frozenset({
    "proc", "sysfs", "devtmpfs", "tmpfs", "devpts",
    "fusectl", "cgroup", "cgroup2", "pstore",
    "securityfs", "selinuxfs", "autofs", "mqueue",
    "hugetlbfs", "configfs", "debugfs", "tracefs",
    "ramfs", "overlay", "squashfs", "nsfs",
    "overlay-rootfs", "fuse.gvfsd-fuse",
})

# ─── Remote filesystem types die we overslaan ───────────────────────
REMOTE_FS: frozenset[str] = frozenset({
    "nfs", "nfs3", "nfs4", "nfs-over-rdma",
    "cifs", "smb", "smb2", "smb3", "cifs_cache",
    "fuse.sshfs", "fuse.glusterfs", "fuse.mergerfs",
    "aoe", "iscsi", "9p", "serverino",
})


def collect_hardware() -> dict:
    """Verzamel CPU- en RAM-metrics.

    Returns:
        dict met cpu_percent, cpu_cores, ram_total_gb, ram_used_gb, ram_percent
    """
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_cores = psutil.cpu_count(logical=True) or 0
    ram = psutil.virtual_memory()

    return {
        "cpu_percent": cpu_percent,
        "cpu_cores": cpu_cores,
        "ram_total_gb": round(ram.total / (1024**3), 2),
        "ram_used_gb": round(ram.used / (1024**3), 2),
        "ram_percent": ram.percent,
    }


# ─── Storage helpers ────────────────────────────────────────────────

def _is_containerized() -> bool:
    """Detecteer of we in een Docker container draaien."""
    return Path("/.dockerenv").exists()


def _is_host_mounted() -> bool:
    """Check of de host-filesystem gemount is op /host/."""
    return Path("/host").is_dir() and Path("/host/proc/mounts").exists()


def _is_physical_device(device: str) -> bool:
    """Check of een device een fysieke schijf is (geen remote/loop/virtueel).

    Ondersteunt:
    - /dev/sd* (SATA, SCSI, USB)
    - /dev/nvme* (NVMe)
    - /dev/vd* (VirtIO)
    - /dev/mmcblk* (eMMC, SD)
    - /dev/md* (Linux RAID)
    - /dev/mapper/* (LVM)
    """
    return any(
        device.startswith(pattern)
        for pattern in (
            "/dev/sd", "/dev/nvme", "/dev/vd", "/dev/mmcblk",
            "/dev/md", "/dev/mapper/",
        )
    )


def _mount_depth(mountpoint: str) -> int:
    """Hoe diep is een mountpoint? / = 0, /data = 1, /data/sub = 2."""
    if mountpoint == "/":
        return 0
    return mountpoint.count("/")


def _read_host_mounts_cached() -> list[dict]:
    """Lees host-schijfmounts van /host/proc/mounts met caching.

    Caching voorkomt herhaalde reads binnen de TTL (5 seconden).
    Dedupliceert per (device, total_gb): bind mounts van hetzelfde
    subvolume worden samengevoegd, BTRFS-subvolumes met verschillende
    capaciteit blijven behouden. Binnen een groep wint de mount met
    de hoogste prioriteit (/ > /run/rugix/mounts/system > ...).

    Returns:
        lijst van dicts met total_gb, used_gb, available_gb, used_percent,
        mount_point, device, fstype
    """
    global _MOUNT_CACHE

    now = time.time()
    if _MOUNT_CACHE["data"] and (now - _MOUNT_CACHE["timestamp"]) < _MOUNT_CACHE_TTL:
        return _MOUNT_CACHE["data"]

    raw_mounts: list[dict] = []
    skip_devices: set[str] = {"none", "tmpfs", "devtmpfs"}

    try:
        content = Path("/host/proc/mounts").read_text()
    except (FileNotFoundError, PermissionError) as e:
        logger.warning("Kan /host/proc/mounts niet lezen: %s", e)
        _MOUNT_CACHE = {"data": [], "timestamp": now}
        return []

    for line in content.strip().splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        device, mountpoint, fstype = parts[0], parts[1], parts[2]

        # Skip pseudo-FS
        if fstype in PSEUDO_FS:
            continue
        # Skip remote FS (NFS, CIFS, …)
        if fstype in REMOTE_FS:
            continue
        # Skip niet-fysieke apparaten
        if device in skip_devices or device.startswith("/dev/loop"):
            continue
        # Skip /boot
        if mountpoint in ("/boot/efi", "/boot/EFI", "/efi", "/boot"):
            continue
        # Alleen fysieke schijven
        if not _is_physical_device(device):
            continue

        # Controleer of het mountpoint bestaat op de host
        host_path = Path(f"/host{mountpoint}")
        if not host_path.is_dir():
            continue

        try:
            usage = psutil.disk_usage(str(host_path))
            raw_mounts.append({
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "available_gb": round(usage.free / (1024**3), 2),
                "used_percent": usage.percent,
                "mount_point": mountpoint,
                "device": device,
                "fstype": fstype,
                "_depth": _mount_depth(mountpoint),
            })
        except (PermissionError, OSError) as e:
            logger.debug("Kan schijfgegevens niet lezen voor %s: %s", mountpoint, e)
            continue

    # ─── Dedupliceer per (device, total_gb) ──────────────────────────
    # Device + total_gb = uniek filesystem (BTRFS-subvolumes hebben
    # verschillende total_gb, dus blijven behouden). Bind mounts van
    # hetzelfde subvolume hebben identieke (device, total_gb) en
    # worden samengevoegd: de mount met hoogste prioriteit wint.
    def _mount_priority(mp: str) -> int:
        """Bepaal prioriteit van een mountpoint (lager = beter)."""
        if mp == "/":
            return 0
        if mp.startswith("/run/rugix/mounts/"):
            suffix = mp[len("/run/rugix/mounts/"):]
            order = {"system": 1, "data": 2, "config": 3}
            return order.get(suffix, 10)
        return 50 + _mount_depth(mp)

    best_per_key: dict[tuple[str, float], dict] = {}
    for m in raw_mounts:
        key = (m["device"], m["total_gb"])
        if key not in best_per_key:
            best_per_key[key] = m
        else:
            existing = best_per_key[key]
            if _mount_priority(m["mount_point"]) < _mount_priority(existing["mount_point"]):
                best_per_key[key] = m
            elif _mount_priority(m["mount_point"]) == _mount_priority(existing["mount_point"]):
                if m["_depth"] < existing["_depth"]:
                    best_per_key[key] = m

    # Sorteer op mount_point
    result = sorted(best_per_key.values(), key=lambda x: x["mount_point"])

    # Verwijder interne velden
    for m in result:
        m.pop("_depth", None)

    _MOUNT_CACHE = {"data": result, "timestamp": now}
    return result


def _collect_storage_native() -> list[dict]:
    """Verzamel opslag via psutil (werkt buiten Docker of als fallback).

    Returns:
        lijst van dicts met opslaginformatie
    """
    storages: list[dict] = []

    for part in psutil.disk_partitions():
        # Skip loop-devices (snap packages)
        if part.device and ("loop" in part.device or "/dev/loop" in part.device):
            continue
        # Skip pseudo-FS, behalve root (/) die in Docker overlay kan zijn
        if part.fstype in PSEUDO_FS and part.mountpoint != "/":
            continue
        # Skip Docker config-bestanden
        if part.mountpoint in ("/etc/resolv.conf", "/etc/hostname", "/etc/hosts"):
            continue
        # Skip als het een bestand is ipv directory
        if os.path.isfile(part.mountpoint):
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
            logger.debug("Geen permissie voor mountpoint: %s", part.mountpoint)
            continue

    return storages


def collect_storage() -> list[dict]:
    """Verzamel schijfruimte van alle fysieke schijven.

    Als we in Docker draaien met de host-filesystem gemount (/host/),
    lezen we van de host. Anders vallen we terug op psutil.

    Returns:
        lijst van dicts met opslaginformatie per schijf
    """
    if _is_containerized() and _is_host_mounted():
        host_mounts = _read_host_mounts_cached()
        if host_mounts:
            logger.info("Host-schijfgegevens gelezen via /host/ (%d schijven)", len(host_mounts))
            return host_mounts
        logger.info("Docker met /host/ gemount maar geen schijven gevonden — fallback naar psutil")

    return _collect_storage_native()
