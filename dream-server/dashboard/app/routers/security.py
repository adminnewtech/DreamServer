"""Security page - certs + fail2ban + ports + processes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..integrations.security import gather_security

router = APIRouter()


@router.get("/security", response_class=HTMLResponse)
async def page_security(request: Request):
    templates = request.app.state.templates
    data = await gather_security()
    return templates.TemplateResponse(
        "pages/security.html",
        {
            "request": request,
            "active_page": "security",
            "data": data,
        },
    )


@router.get("/api/security")
async def api_security():
    return JSONResponse(await gather_security())
