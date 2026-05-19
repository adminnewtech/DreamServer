"""SSL certificates, fail2ban jails, listening ports, top processes."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from pathlib import Path

from ..health import _run_cmd

log = logging.getLogger("dream-dashboard.security")

LE_DIR = Path("/etc/letsencrypt/live")


async def le_certs() -> list[dict]:
    if not LE_DIR.exists():
        return []
    out = []
    for d in sorted(LE_DIR.iterdir()):
        if not d.is_dir():
            continue
        cert = d / "fullchain.pem"
        if not cert.exists():
            continue
        rc, txt = await _run_cmd(
            [
                "openssl",
                "x509",
                "-in",
                str(cert),
                "-noout",
                "-enddate",
                "-issuer",
                "-subject",
            ],
            timeout=3.0,
        )
        if rc != 0:
            out.append({"name": d.name, "error": txt[:120]})
            continue
        info = {"name": d.name}
        for line in txt.splitlines():
            if line.startswith("notAfter="):
                try:
                    end = dt.datetime.strptime(
                        line.split("=", 1)[1].strip(), "%b %d %H:%M:%S %Y %Z"
                    )
                    days = (end - dt.datetime.utcnow()).days
                    info["expires"] = end.strftime("%Y-%m-%d")
                    info["days_left"] = days
                    info["status"] = (
                        "ok" if days > 30 else "warn" if days > 7 else "critical"
                    )
                except Exception as e:
                    info["error"] = str(e)
            elif line.startswith("issuer="):
                info["issuer"] = line.split("=", 1)[1].strip()[:80]
            elif line.startswith("subject="):
                info["subject"] = line.split("=", 1)[1].strip()[:80]
        out.append(info)
    out.sort(key=lambda c: c.get("days_left", 9999))
    return out


async def fail2ban_status() -> dict:
    rc, out = await _run_cmd(["fail2ban-client", "status"], timeout=5.0)
    if rc != 0:
        return {"error": out[:200]}
    jails = []
    m = re.search(r"Jail list:\s*(.+)", out)
    if m:
        jails = [j.strip() for j in m.group(1).split(",") if j.strip()]
    details = []
    for j in jails:
        rc, jail_out = await _run_cmd(["fail2ban-client", "status", j], timeout=4.0)
        info = {"jail": j}
        if rc == 0:
            for line in jail_out.splitlines():
                if "Currently failed:" in line:
                    info["failed"] = int(line.split(":")[-1].strip())
                elif "Currently banned:" in line:
                    info["banned"] = int(line.split(":")[-1].strip())
                elif "Banned IP list:" in line:
                    ips = line.split(":", 1)[1].strip()
                    info["banned_ips"] = ips.split() if ips else []
                elif "Total banned:" in line:
                    info["total_banned"] = int(line.split(":")[-1].strip())
        details.append(info)
    return {"jails": details}


async def listening_ports() -> list[dict]:
    rc, out = await _run_cmd(["ss", "-tlnp"], timeout=5.0)
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[3]
        if ":" in local:
            addr, port = local.rsplit(":", 1)
        else:
            continue
        users_field = " ".join(parts[5:]) if len(parts) > 5 else ""
        # users:(("nginx",pid=1023,fd=11))
        m = re.search(r'\("([^"]+)"', users_field)
        process = m.group(1) if m else ""
        rows.append({"address": addr, "port": port, "process": process})
    return sorted(rows, key=lambda r: int(r["port"]) if r["port"].isdigit() else 99999)


async def top_processes(n: int = 15) -> list[dict]:
    rc, out = await _run_cmd(
        ["ps", "-eo", "pid,user,pcpu,pmem,comm", "--sort=-pcpu"],
        timeout=4.0,
    )
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines()[1 : n + 1]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        rows.append(
            {
                "pid": parts[0],
                "user": parts[1],
                "cpu": float(parts[2]),
                "mem": float(parts[3]),
                "command": parts[4][:60],
            }
        )
    return rows


async def gather_security() -> dict:
    certs, f2b, ports, procs = await asyncio.gather(
        le_certs(),
        fail2ban_status(),
        listening_ports(),
        top_processes(),
        return_exceptions=True,
    )
    return {
        "certs": certs if not isinstance(certs, Exception) else [],
        "fail2ban": f2b if not isinstance(f2b, Exception) else {"error": str(f2b)},
        "ports": ports if not isinstance(ports, Exception) else [],
        "processes": procs if not isinstance(procs, Exception) else [],
    }
