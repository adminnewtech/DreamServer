"""Login/logout - simple PIN cookie."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import COOKIE_MAX_AGE, COOKIE_NAME, check_pin, is_logged_in
from ..config import ADMIN_PIN

router = APIRouter(prefix="/auth")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "pages/login.html",
        {
            "request": request,
            "active_page": None,
            "logged_in": is_logged_in(request),
            "next": next,
            "pin_enabled": bool(ADMIN_PIN),
        },
    )


@router.post("/login")
async def login_submit(request: Request, pin: str = Form(...), next: str = Form("/")):
    if not check_pin(pin):
        raise HTTPException(401, "wrong PIN")
    resp = RedirectResponse(next, status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        ADMIN_PIN,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return resp


@router.post("/logout")
async def logout():
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp
