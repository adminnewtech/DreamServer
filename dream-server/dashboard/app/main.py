"""Dream Dashboard - VPS service status board.

Routes:
  GET /             -> full HTML dashboard
  GET /api/health   -> JSON health for all services
  GET /api/system   -> JSON host metrics
  GET /partial/grid -> HTML fragment for HTMX auto-refresh
  GET /logs/<unit>  -> last 50 journal lines for a systemd unit
  GET /healthz      -> dashboard self-check
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .health import _run_cmd, probe_all, system_summary
from .services import GROUPS, LOGINS, all_services

BASE = Path(__file__).parent
TPL = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(
    title="Dream Dashboard",
    description="Live status of every service running on the VPS",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

SHOW_LOGINS = os.environ.get("DASHBOARD_SHOW_LOGINS", "1") == "1"


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    services = await probe_all(all_services())
    sys_info = await system_summary()
    by_group: dict[str, list[dict]] = {}
    for s in services:
        by_group.setdefault(s["group"], []).append(s)
    totals = {
        "total": len(services),
        "up": sum(1 for s in services if s["status"] == "up"),
        "down": sum(1 for s in services if s["status"] in ("down", "missing")),
        "degraded": sum(1 for s in services if s["status"] == "degraded"),
    }
    return TPL.TemplateResponse(
        "index.html",
        {
            "request": request,
            "groups": GROUPS,
            "by_group": by_group,
            "sys": sys_info,
            "totals": totals,
            "logins": LOGINS if SHOW_LOGINS else {},
            "show_logins": SHOW_LOGINS,
        },
    )


@app.get("/partial/grid", response_class=HTMLResponse)
async def partial_grid(request: Request):
    services = await probe_all(all_services())
    sys_info = await system_summary()
    by_group: dict[str, list[dict]] = {}
    for s in services:
        by_group.setdefault(s["group"], []).append(s)
    totals = {
        "total": len(services),
        "up": sum(1 for s in services if s["status"] == "up"),
        "down": sum(1 for s in services if s["status"] in ("down", "missing")),
        "degraded": sum(1 for s in services if s["status"] == "degraded"),
    }
    return TPL.TemplateResponse(
        "_grid.html",
        {
            "request": request,
            "groups": GROUPS,
            "by_group": by_group,
            "sys": sys_info,
            "totals": totals,
        },
    )


@app.get("/api/health")
async def api_health():
    services = await probe_all(all_services())
    return JSONResponse(services)


@app.get("/api/system")
async def api_system():
    return JSONResponse(await system_summary())


@app.get("/logs/{unit}", response_class=PlainTextResponse)
async def logs(unit: str):
    valid = {s.get("unit") for grp in GROUPS.values() for s in grp["services"]}
    valid.discard(None)
    if unit not in valid:
        raise HTTPException(status_code=404, detail="unknown unit")
    rc, out = await _run_cmd(
        ["journalctl", "-u", unit, "-n", "50", "--no-pager", "--output=short-iso"],
        timeout=5.0,
    )
    return out or "(no log lines)"
