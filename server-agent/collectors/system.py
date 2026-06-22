"""Verzamelt hardware metrics (CPU, RAM) en opslag-info.

Gebruikt psutil voor cross-platform compatibiliteit.
In Docker worden host-schijven gelezen via /host/ als die gemount zijn.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)

# Filesystem types die we overslaan (pseudo/virtueel)
PSEUDO_FS = frozenset({
    "proc", "sysfs", "devtmpfs", "tmpfs", "devpts",
    "fusectl", "cgroup", "cgroup2", "pstore",
    "securityfs", "selinuxfs", "autofs", "mqueue",
    "hugetlbfs", "configfs", "debugfs", "tracefs",
    "ramfs", "overlay", "squashfs", "nsfs",
    "overlay-rootfs", "fuse.gvfsd-fuse",
})


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


def _is_docker_with_host() -> bool:
    """Check of we in Docker draaien met de host-filesystem gemount."""
    return Path("/host").is_dir() and Path("/host/proc/mounts").exists()


def _is_physical_device(device: str) -> bool:
    """Check of een device een fysieke schijf is (geen remote/loop/virtueel)."""
    return (
        device.startswith("/dev/sd")
        or device.startswith("/dev/nvme")
        or device.startswith("/dev/vd")
        or device.startswith("/dev/mmcblk")
    )


def _mount_depth(mountpoint: str) -> int:
    """Hoe diep is een mountpoint? / is diepte 0, /data is diepte 1, /data/sub is diepte 2."""
    if mountpoint == "/":
        return 0
    return mountpoint.count("/")


def _read_host_mounts() -> list[dict]:
    """Lees host-schijfmounts van /host/proc/mounts (wanneer beschikbaar).

    Dedupliceert per device: als één fysieke schijf meerdere mountpoints heeft
    (bv. /data, /home, /var/lib/docker allemaal op /dev/sda6), dan tonen we
    enkel de **ondiepste** mount (de root-mount van die partitie).
    Remote mounts (NFS, CIFS, SSHFS) worden overgeslagen.
    """
    pseudo_fs = {
        "proc", "sysfs", "devtmpfs", "tmpfs", "devpts",
        "fusectl", "cgroup", "cgroup2", "pstore",
        "securityfs", "selinuxfs", "autofs", "mqueue",
        "hugetlbfs", "configfs", "debugfs", "tracefs",
        "ramfs", "nsfs", "fuse.gvfsd-fuse",
    }
    # Remote filesystem types die we overslaan
    remote_fs = {"nfs", "nfs4", "cifs", "smb3", "fuse.sshfs", "fuse.glusterfs"}

    skip_devices = {"none", "tmpfs", "devtmpfs"}

    raw_mounts = []
    try:
        content = Path("/host/proc/mounts").read_text()
        for line in content.strip().splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            device, mountpoint, fstype = parts[0], parts[1], parts[2]

            # Sla pseudo-filesystems over
            if fstype in pseudo_fs:
                continue
            # Sla remote filesystems over (NFS, CIFS, …)
            if fstype in remote_fs:
                continue
            # Sla niet-apparaten over
            if device in skip_devices:
                continue
            # Sla loop-devices over (snap packages, enz.)
            if device.startswith("/dev/loop"):
                continue
            # Sla /boot/efi en vergelijkbare kleine mounts over
            if mountpoint in ("/boot/efi", "/boot/EFI", "/efi"):
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
    except (FileNotFoundError, PermissionError) as e:
        logger.warning("Kan /host/proc/mounts niet lezen: %s", e)

    # ─── Dedupliceer per device ─────────────────────────────────────
    # Houd voor elk uniek device enkel de ondiepste mount over
    best_per_device: dict[str, dict] = {}
    for m in raw_mounts:
        dev = m["device"]
        if dev not in best_per_device or m["_depth"] < best_per_device[dev]["_depth"]:
            best_per_device[dev] = m

    # Sorteer op mount_point voor een mooie volgorde
    result = sorted(best_per_device.values(), key=lambda x: x["mount_point"])

    # Verwijder interne _depth veld
    for m in result:
        del m["_depth"]

    return result


def _collect_storage_native() -> list:
    """Verzamel opslag via psutil (werkt buiten Docker of als fallback)."""
    storages = []
    for part in psutil.disk_partitions():
        # Sla loop-apparaten over (snap-packages, enz.)
        if part.device and "loop" in part.device:
            continue
        # Sla pseudo-FS over, behalve root (/) die in Docker overlay kan zijn
        if part.fstype in PSEUDO_FS and part.mountpoint != "/":
            continue
        # Sla Docker-config-bestanden over (bind mounts)
        if part.mountpoint in ("/etc/resolv.conf", "/etc/hostname", "/etc/hosts"):
            continue
        # Sla mount points over die geen directory zijn
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
            continue
    return storages


def collect_storage() -> list:
    """Geeft schijfruimte van alle fysieke schijven.

    Als we in Docker draaien met de host-filesystem gemount (/host/),
    lezen we van de host. Anders vallen we terug op psutil.
    """
    if _is_docker_with_host():
        host_mounts = _read_host_mounts()
        if host_mounts:
            logger.info("Host-schijfgegevens gelezen via /host/ (%d schijven)", len(host_mounts))
            return host_mounts
        logger.info("Docker met /host/ gemount, maar geen schijven gevonden — fallback naar psutil")

    return _collect_storage_native()
