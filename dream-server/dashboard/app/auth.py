"""Lightweight PIN-based auth for write actions.

Read endpoints (GET /, /api/health, etc.) are open; write endpoints
(POST /actions/*, /assistant) require the PIN cookie set via /login.
"""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

from .config import ADMIN_PIN

COOKIE_NAME = "dream_pin"
COOKIE_MAX_AGE = 60 * 60 * 12  # 12 hours


def check_pin(supplied: str) -> bool:
    if not ADMIN_PIN:
        return False
    return hmac.compare_digest(supplied or "", ADMIN_PIN)


def require_admin(request: Request) -> str:
    """Raise 401 unless a valid PIN cookie is present.

    Returns the actor string for audit logs.
    """
    if not ADMIN_PIN:
        raise HTTPException(
            status_code=503,
            detail="Write actions disabled: set DASHBOARD_ADMIN_PIN to enable.",
        )
    cookie = request.cookies.get(COOKIE_NAME, "")
    if not check_pin(cookie):
        raise HTTPException(status_code=401, detail="PIN required")
    # Actor = client IP (no user accounts yet)
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    return f"pin@{ip}"


def is_logged_in(request: Request) -> bool:
    if not ADMIN_PIN:
        return False
    return check_pin(request.cookies.get(COOKIE_NAME, ""))
