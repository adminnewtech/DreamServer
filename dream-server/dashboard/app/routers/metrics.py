"""Metrics page + JSON time-series API."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import storage
from ..services import all_services

router = APIRouter()


@router.get("/metrics", response_class=HTMLResponse)
async def page_metrics(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/metrics.html",
        {
            "request": request,
            "active_page": "metrics",
            "service_names": [s["name"] for s in all_services()],
        },
    )


@router.get("/api/metrics/host")
async def api_metrics_host(hours: int = 24):
    return JSONResponse(storage.host_history(hours=max(1, min(hours, 48))))


@router.get("/api/metrics/service/{name}")
async def api_metrics_service(name: str, hours: int = 24):
    return JSONResponse(storage.service_history(name, hours=max(1, min(hours, 48))))
