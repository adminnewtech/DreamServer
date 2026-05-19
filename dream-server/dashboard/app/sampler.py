"""Background sampler - polls host + services every N seconds, writes to SQLite."""

from __future__ import annotations

import asyncio
import logging

from . import storage
from .config import METRICS_SAMPLE_INTERVAL_S
from .health import _run_cmd, probe_all, system_summary
from .services import all_services

log = logging.getLogger("dream-dashboard.sampler")

# Track CPU deltas for /proc/stat sampling
_prev_cpu: tuple[int, int] | None = None


async def _host_sample() -> dict:
    """Return cpu_pct, load1, mem_pct, mem_total_gb, disk_pct."""
    global _prev_cpu
    sample: dict = {}

    # CPU delta
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()[1:]
            total = sum(int(p) for p in parts)
            idle = int(parts[3]) + int(parts[4])
        if _prev_cpu:
            d_total = total - _prev_cpu[0]
            d_idle = idle - _prev_cpu[1]
            sample["cpu_pct"] = round(100 * (1 - d_idle / d_total), 1) if d_total else 0
        _prev_cpu = (total, idle)
    except Exception as e:
        log.warning("cpu sample failed: %s", e)

    # Reuse system_summary for mem/disk/load
    s = await system_summary()
    sample["load1"] = (
        float(s.get("load", "0").split("/")[0].strip() or 0) if s.get("load") else None
    )
    sample["mem_pct"] = s.get("mem_used_pct")
    sample["mem_total_gb"] = s.get("mem_total_gb")
    disk = s.get("disk_used_pct", "0%").rstrip("%")
    try:
        sample["disk_pct"] = float(disk)
    except ValueError:
        sample["disk_pct"] = None
    return sample


async def _container_stats() -> dict[str, dict]:
    """Map container_name -> {cpu_pct, mem_mb} via `docker stats --no-stream`."""
    rc, out = await _run_cmd(
        [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}",
        ],
        timeout=10.0,
    )
    if rc != 0:
        return {}
    result: dict[str, dict] = {}
    for line in out.splitlines():
        try:
            name, cpu, mem = line.split("|", 2)
            cpu_pct = float(cpu.replace("%", "").strip())
            mem_used = mem.split("/")[0].strip()
            mem_mb = _parse_mem(mem_used)
            result[name.strip()] = {"cpu_pct": cpu_pct, "mem_mb": mem_mb}
        except Exception:
            continue
    return result


def _parse_mem(s: str) -> float:
    """Parse '128.4MiB' / '1.2GiB' to MB."""
    s = s.strip()
    if not s:
        return 0
    try:
        if s.endswith("GiB") or s.endswith("GB"):
            return float(s.rstrip("GiB").rstrip("GB")) * 1024
        if s.endswith("MiB") or s.endswith("MB"):
            return float(s.rstrip("MiB").rstrip("MB"))
        if s.endswith("KiB") or s.endswith("kB"):
            return float(s.rstrip("KiB").rstrip("kB")) / 1024
        return float(s)
    except ValueError:
        return 0


async def _systemd_resource(unit: str) -> tuple[float | None, float | None]:
    """Get MemoryCurrent + CPUUsageNSec delta for a systemd unit."""
    rc, out = await _run_cmd(
        ["systemctl", "show", unit, "-p", "MemoryCurrent", "-p", "CPUUsageNSec"],
        timeout=3.0,
    )
    if rc != 0:
        return None, None
    props = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            props[k] = v
    mem_bytes = props.get("MemoryCurrent")
    mem_mb = (
        round(int(mem_bytes) / 1024 / 1024, 1)
        if mem_bytes and mem_bytes.isdigit()
        else None
    )
    return None, mem_mb  # CPU% would need deltas; skip for now


async def sample_once() -> None:
    """One sampling pass: host + all services."""
    storage.init_db()
    host = await _host_sample()
    storage.write_host_sample(host)

    services = all_services()
    health = await probe_all(services)
    containers = await _container_stats()

    samples = []
    for svc in health:
        cpu_pct = None
        mem_mb = None
        if svc["kind"] == "docker" and svc.get("container") in containers:
            stat = containers[svc["container"]]
            cpu_pct = stat["cpu_pct"]
            mem_mb = stat["mem_mb"]
        elif svc["kind"] == "systemd" and svc.get("unit"):
            _, mem_mb = await _systemd_resource(svc["unit"])
        samples.append(
            {
                "name": svc["name"],
                "status": svc["status"],
                "cpu_pct": cpu_pct,
                "mem_mb": mem_mb,
            }
        )
    storage.write_service_samples(samples)
    storage.prune()


async def run_forever() -> None:
    while True:
        try:
            await sample_once()
        except Exception as e:
            log.exception("sampler error: %s", e)
        await asyncio.sleep(METRICS_SAMPLE_INTERVAL_S)
