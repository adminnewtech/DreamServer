"""Services overview - the original page, refactored."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..auth import is_logged_in
from ..config import HOST_LABEL, SHOW_LOGINS
from ..health import probe_all, system_summary
from ..services import GROUPS, LOGINS, all_services

router = APIRouter()


def _build_context(services, summary):
    by_group: dict[str, list[dict]] = {}
    for s in services:
        by_group.setdefault(s["group"], []).append(s)
    totals = {
        "total": len(services),
        "up": sum(1 for s in services if s["status"] == "up"),
        "down": sum(1 for s in services if s["status"] in ("down", "missing")),
        "degraded": sum(1 for s in services if s["status"] == "degraded"),
    }
    return by_group, totals


@router.get("/", response_class=HTMLResponse)
async def page_services(request: Request):
    services = await probe_all(all_services())
    sys_info = await system_summary()
    by_group, totals = _build_context(services, sys_info)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/services.html",
        {
            "request": request,
            "active_page": "services",
            "groups": GROUPS,
            "by_group": by_group,
            "sys": sys_info,
            "totals": totals,
            "host": HOST_LABEL,
            "logins": LOGINS if SHOW_LOGINS else {},
            "show_logins": SHOW_LOGINS,
            "admin_logged_in": is_logged_in(request),
        },
    )


@router.get("/partial/grid", response_class=HTMLResponse)
async def partial_grid(request: Request):
    services = await probe_all(all_services())
    sys_info = await system_summary()
    by_group, totals = _build_context(services, sys_info)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/grid.html",
        {
            "request": request,
            "groups": GROUPS,
            "by_group": by_group,
            "sys": sys_info,
            "totals": totals,
            "admin_logged_in": is_logged_in(request),
        },
    )


@router.get("/api/health")
async def api_health():
    services = await probe_all(all_services())
    return JSONResponse(services)


@router.get("/api/system")
async def api_system():
    return JSONResponse(await system_summary())
