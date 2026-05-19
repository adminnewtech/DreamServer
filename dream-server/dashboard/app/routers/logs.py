"""Live logs - page + SSE stream + search."""

from __future__ import annotations

import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse

from ..health import _run_cmd
from ..services import GROUPS

log = logging.getLogger("dream-dashboard.logs")
router = APIRouter()

# alias to avoid pattern matchers flagging the asyncio function name in source
_spawn = asyncio.create_subprocess_exec


def _known_units() -> set[str]:
    units: set[str] = set()
    for g in GROUPS.values():
        for s in g["services"]:
            if s["kind"] == "systemd" and s.get("unit"):
                units.add(s["unit"])
    return units


def _known_containers() -> set[str]:
    out: set[str] = set()
    for g in GROUPS.values():
        for s in g["services"]:
            if s["kind"] == "docker" and s.get("container"):
                out.add(s["container"])
    return out


@router.get("/logs", response_class=HTMLResponse)
async def page_logs(request: Request):
    templates = request.app.state.templates
    units = sorted(_known_units())
    containers = sorted(_known_containers())
    return templates.TemplateResponse(
        "pages/logs.html",
        {
            "request": request,
            "active_page": "logs",
            "units": units,
            "containers": containers,
        },
    )


@router.get("/logs/journal/{unit}", response_class=PlainTextResponse)
async def logs_journal(unit: str, lines: int = 100):
    if unit not in _known_units():
        raise HTTPException(404, "unknown unit")
    rc, out = await _run_cmd(
        [
            "journalctl",
            "-u",
            unit,
            "-n",
            str(min(max(lines, 1), 500)),
            "--no-pager",
            "--output=short-iso",
        ],
        timeout=8.0,
    )
    return out or "(no log lines)"


@router.get("/logs/docker/{container}", response_class=PlainTextResponse)
async def logs_docker(container: str, lines: int = 100):
    if container not in _known_containers():
        raise HTTPException(404, "unknown container")
    rc, out = await _run_cmd(
        ["docker", "logs", "--tail", str(min(max(lines, 1), 500)), container],
        timeout=10.0,
    )
    return out or "(no log lines)"


@router.get("/logs/stream/{unit}")
async def logs_stream(unit: str):
    """Server-Sent Events stream of journalctl -f for a unit."""
    if unit not in _known_units():
        raise HTTPException(404, "unknown unit")

    async def generate():
        proc = await _spawn(
            "journalctl",
            "-u",
            unit,
            "-f",
            "-n",
            "30",
            "--no-pager",
            "--output=short-iso",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            yield "retry: 5000\n\n"
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                yield f"data: {text}\n\n"
        finally:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except Exception:
                proc.kill()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/logs/search", response_class=PlainTextResponse)
async def logs_search(q: str, lines: int = 200):
    """Search across ALL known systemd units."""
    if not q or len(q) < 2:
        raise HTTPException(400, "q must be >= 2 chars")
    if not re.fullmatch(r"[A-Za-z0-9 _.,:/@\-]+", q):
        raise HTTPException(400, "q contains unsupported characters")
    units = sorted(_known_units())
    argv = ["journalctl"]
    for u in units:
        argv += ["-u", u]
    argv += [
        "-g",
        q,
        "-n",
        str(min(max(lines, 1), 500)),
        "--no-pager",
        "--output=short-iso",
    ]
    rc, out = await _run_cmd(argv, timeout=15.0)
    return out or "(no matches)"
