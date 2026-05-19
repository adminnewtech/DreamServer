"""Overview page - the new landing page with KPI cards from all systems."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..auth import is_logged_in
from ..config import HOST_LABEL
from ..health import probe_all, system_summary
from ..integrations.clients import gather_all
from ..services import all_services

router = APIRouter()


@router.get("/overview", response_class=HTMLResponse)
async def page_overview(request: Request):
    services = await probe_all(all_services())
    sys_info = await system_summary()
    integrations = await gather_all()

    totals = {
        "total": len(services),
        "up": sum(1 for s in services if s["status"] == "up"),
        "down": sum(1 for s in services if s["status"] in ("down", "missing")),
        "degraded": sum(1 for s in services if s["status"] == "degraded"),
    }
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/overview.html",
        {
            "request": request,
            "active_page": "overview",
            "sys": sys_info,
            "totals": totals,
            "host": HOST_LABEL,
            "integrations": integrations,
            "admin_logged_in": is_logged_in(request),
        },
    )


@router.get("/api/integrations")
async def api_integrations():
    return JSONResponse(await gather_all())
