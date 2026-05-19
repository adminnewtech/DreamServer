"""Databases page - Postgres + Redis inspector."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..integrations.databases import inspect_all

router = APIRouter()


@router.get("/databases", response_class=HTMLResponse)
async def page_databases(request: Request):
    templates = request.app.state.templates
    data = await inspect_all()
    return templates.TemplateResponse(
        "pages/databases.html",
        {
            "request": request,
            "active_page": "databases",
            "data": data,
        },
    )


@router.get("/api/databases")
async def api_databases():
    return JSONResponse(await inspect_all())
