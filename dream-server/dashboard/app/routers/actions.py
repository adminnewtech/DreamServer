"""POST /actions/* - restart/stop/start systemd units and Docker containers.

Requires PIN cookie set via /auth/login.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .. import storage
from ..auth import require_admin
from ..health import _run_cmd
from ..services import all_services

log = logging.getLogger("dream-dashboard.actions")

router = APIRouter(prefix="/actions")

_VALID_ACTIONS = {"restart", "stop", "start"}
_UNIT_RE = re.compile(r"^[A-Za-z0-9._@\-]+$")


def _valid_unit(unit: str) -> bool:
    return bool(_UNIT_RE.fullmatch(unit))


def _known_units() -> set[str]:
    return {
        s["unit"] for s in all_services() if s["kind"] == "systemd" and s.get("unit")
    }


def _known_containers() -> set[str]:
    return {
        s["container"]
        for s in all_services()
        if s["kind"] == "docker" and s.get("container")
    }


@router.post("/systemd/{unit}/{action}")
async def systemd_action(
    unit: str,
    action: str,
    request: Request,
    actor: str = Depends(require_admin),
):
    if action not in _VALID_ACTIONS:
        raise HTTPException(400, "invalid action")
    if not _valid_unit(unit) or unit not in _known_units():
        raise HTTPException(404, "unknown unit")
    rc, out = await _run_cmd(["systemctl", action, unit], timeout=20.0)
    result = "ok" if rc == 0 else "error"
    storage.audit(actor, f"systemd:{action}", unit, result, out[:400])
    return JSONResponse({"ok": rc == 0, "rc": rc, "output": out[:400]})


@router.post("/docker/{container}/{action}")
async def docker_action(
    container: str,
    action: str,
    request: Request,
    actor: str = Depends(require_admin),
):
    if action not in _VALID_ACTIONS:
        raise HTTPException(400, "invalid action")
    if not _valid_unit(container) or container not in _known_containers():
        raise HTTPException(404, "unknown container")
    rc, out = await _run_cmd(["docker", action, container], timeout=30.0)
    result = "ok" if rc == 0 else "error"
    storage.audit(actor, f"docker:{action}", container, result, out[:400])
    return JSONResponse({"ok": rc == 0, "rc": rc, "output": out[:400]})


@router.get("/audit")
async def audit_log_view(actor: str = Depends(require_admin)):
    return JSONResponse(storage.audit_recent(100))
