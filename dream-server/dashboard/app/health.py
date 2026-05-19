"""Health probes - async, cached, fast.

Strategy per kind:
  systemd:  systemctl is-active <unit>
  docker:   docker inspect for state + health
  http:     GET <url> with 3s timeout
  pg/redis: TCP connect
  process:  pgrep -f <name>

Results cached for CACHE_TTL seconds to avoid hammering on dashboard refresh.
"""

from __future__ import annotations

import asyncio
import socket
import time

import httpx

CACHE_TTL = 8  # seconds - slightly less than UI auto-refresh (10s)

_cache: dict[str, tuple[float, dict]] = {}


def _cache_get(key: str) -> dict | None:
    hit = _cache.get(key)
    if not hit:
        return None
    ts, value = hit
    if time.time() - ts > CACHE_TTL:
        return None
    return value


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)


async def _run_cmd(argv: list[str], timeout: float = 5.0) -> tuple[int, str]:
    """Run a command with argv list (no shell). Safe by construction."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode("utf-8", errors="replace").strip()
    except (asyncio.TimeoutError, FileNotFoundError) as e:
        return 1, str(e)


async def probe_systemd(unit: str) -> dict:
    cached = _cache_get(f"systemd:{unit}")
    if cached:
        return cached
    rc, out = await _run_cmd(["systemctl", "is-active", unit])
    status = "up" if out == "active" else "down"
    detail = out or "unknown"
    if status == "down":
        # capture last journal line for context
        _, log = await _run_cmd(
            ["journalctl", "-u", unit, "-n", "1", "--no-pager", "--output=cat"],
            timeout=3.0,
        )
        if log:
            detail = log[:200]
    result = {"status": status, "detail": detail}
    _cache_set(f"systemd:{unit}", result)
    return result


async def probe_docker(container: str) -> dict:
    cached = _cache_get(f"docker:{container}")
    if cached:
        return cached
    fmt = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}"
    rc, out = await _run_cmd(
        ["docker", "inspect", "--format", fmt, container],
        timeout=5.0,
    )
    if rc != 0:
        result = {"status": "missing", "detail": out[:200]}
    else:
        parts = (out.split("|", 1) + ["n/a"])[:2]
        state, health = parts[0], parts[1]
        if state == "running" and health in ("healthy", "n/a"):
            result = {"status": "up", "detail": f"{state}/{health}"}
        elif state == "running":
            result = {"status": "degraded", "detail": f"{state}/{health}"}
        else:
            result = {"status": "down", "detail": f"{state}/{health}"}
    _cache_set(f"docker:{container}", result)
    return result


async def probe_http(url: str) -> dict:
    cached = _cache_get(f"http:{url}")
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(
            timeout=3.0, verify=False, follow_redirects=False
        ) as c:
            r = await c.get(url)
            ok = 200 <= r.status_code < 500
            result = {
                "status": "up" if ok else "down",
                "detail": f"HTTP {r.status_code}",
            }
    except Exception as e:
        result = {"status": "down", "detail": str(e)[:200]}
    _cache_set(f"http:{url}", result)
    return result


def probe_tcp(host: str, port: int) -> dict:
    cached = _cache_get(f"tcp:{host}:{port}")
    if cached:
        return cached
    try:
        with socket.create_connection((host, port), timeout=2.0):
            result = {"status": "up", "detail": f"tcp {host}:{port}"}
    except Exception as e:
        result = {"status": "down", "detail": str(e)[:200]}
    _cache_set(f"tcp:{host}:{port}", result)
    return result


async def probe_process(name: str) -> dict:
    cached = _cache_get(f"proc:{name}")
    if cached:
        return cached
    rc, out = await _run_cmd(["pgrep", "-f", name], timeout=3.0)
    result = {
        "status": "up" if rc == 0 and out else "down",
        "detail": out[:80] if out else "no pid",
    }
    _cache_set(f"proc:{name}", result)
    return result


async def probe_one(svc: dict) -> dict:
    kind = svc["kind"]
    if kind == "systemd":
        return await probe_systemd(svc["unit"])
    if kind == "docker":
        return await probe_docker(svc["container"])
    if kind == "http":
        return await probe_http(svc["url"])
    if kind == "process":
        return await probe_process(svc["process"])
    if kind in ("pg", "redis"):
        return probe_tcp("127.0.0.1", svc["port"])
    return {"status": "unknown", "detail": f"no probe for kind={kind}"}


async def probe_all(services: list[dict]) -> list[dict]:
    """Run all probes concurrently, attach results."""
    results = await asyncio.gather(
        *[probe_one(s) for s in services], return_exceptions=True
    )
    out = []
    for svc, res in zip(services, results):
        if isinstance(res, Exception):
            res = {"status": "error", "detail": str(res)[:200]}
        out.append({**svc, **res})
    return out


async def system_summary() -> dict:
    """Quick host metrics: uptime, load, mem, disk."""
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
        with open("/proc/loadavg") as f:
            load = f.read().split()[:3]
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0])
        mem_total = mem.get("MemTotal", 0)
        mem_avail = mem.get("MemAvailable", 0)
        mem_used_pct = (
            round(100 * (mem_total - mem_avail) / mem_total, 1) if mem_total else 0
        )
        rc, df_out = await _run_cmd(["df", "-h", "/"], timeout=3.0)
        disk_used = "?"
        if rc == 0:
            lines = df_out.splitlines()
            if len(lines) > 1:
                disk_used = lines[1].split()[4]
        return {
            "uptime_h": round(uptime_sec / 3600, 1),
            "load": " / ".join(load),
            "mem_used_pct": mem_used_pct,
            "mem_total_gb": round(mem_total / 1024 / 1024, 1),
            "disk_used_pct": disk_used,
        }
    except Exception as e:
        return {"error": str(e)[:200]}
