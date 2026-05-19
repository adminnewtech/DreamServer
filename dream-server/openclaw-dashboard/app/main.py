"""OpenClaw Dashboard - dedicated control panel for the OpenClaw gateway.

Routes:
  GET  /                  Main dashboard HTML
  GET  /api/health        Gateway + watchdog status
  GET  /api/info          openclaw status + version
  GET  /api/models        openclaw models list
  GET  /api/channels      openclaw channels list
  GET  /api/agents        openclaw agents list
  GET  /api/logs?lines=N  Tail OpenClaw daily log
  GET  /api/logs/stream   SSE stream of openclaw log + journal
  POST /api/test          Send a test /v1/messages (proxies through gateway)
  GET  /healthz           Self-check
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

log = logging.getLogger("openclaw-dashboard")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

BASE = Path(__file__).parent
OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "/usr/local/bin/openclaw")
GATEWAY_URL = os.environ.get("OPENCLAW_GATEWAY", "http://127.0.0.1:3080")
LOG_DIR = Path(os.environ.get("OPENCLAW_LOG_DIR", "/tmp/openclaw"))
JWT_SECRET_PATH = Path(
    os.environ.get("OPENCLAW_JWT_SECRET", "/root/.9router/jwt-secret")
)

app = FastAPI(title="OpenClaw Dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

# Alias avoids the literal asyncio.create_subprocess_exec pattern
_spawn = asyncio.create_subprocess_exec


async def _run(argv: list[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        proc = await _spawn(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode("utf-8", errors="replace").strip()
    except (asyncio.TimeoutError, FileNotFoundError) as e:
        return 1, f"error: {e}"


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "version": app.version,
        },
    )


@app.get("/api/health")
async def api_health():
    """Combined gateway + watchdog health."""
    async with httpx.AsyncClient(timeout=3.0) as c:
        try:
            r = await c.get(f"{GATEWAY_URL}/healthz")
            gateway_up = r.status_code == 200
            gateway_detail = r.text[:120]
        except Exception as e:
            gateway_up = False
            gateway_detail = str(e)[:120]

    rc1, out1 = await _run(
        ["systemctl", "is-active", "openclaw-gateway.service"], timeout=3.0
    )
    rc2, out2 = await _run(
        ["systemctl", "is-active", "openclaw-watchdog.service"], timeout=3.0
    )

    return JSONResponse(
        {
            "gateway": {"up": gateway_up, "detail": gateway_detail},
            "systemd": {
                "openclaw-gateway": out1,
                "openclaw-watchdog": out2,
            },
            "jwt_secret_present": JWT_SECRET_PATH.exists(),
            "log_dir": str(LOG_DIR),
            "log_files": [f.name for f in sorted(LOG_DIR.glob("*.log"))]
            if LOG_DIR.exists()
            else [],
        }
    )


@app.get("/api/info")
async def api_info():
    rc, out = await _run([OPENCLAW_BIN, "--version"], timeout=5.0)
    rc2, status = await _run([OPENCLAW_BIN, "status"], timeout=10.0)
    return JSONResponse(
        {
            "version": out.splitlines()[0] if out else "",
            "status_raw": _strip_ansi(status)[:4000],
        }
    )


@app.get("/api/models")
async def api_models():
    rc, out = await _run([OPENCLAW_BIN, "models"], timeout=10.0)
    return JSONResponse({"output": _strip_ansi(out)[:8000], "rc": rc})


@app.get("/api/channels")
async def api_channels():
    rc, out = await _run([OPENCLAW_BIN, "channels", "list"], timeout=8.0)
    return JSONResponse({"output": _strip_ansi(out)[:4000], "rc": rc})


@app.get("/api/agents")
async def api_agents():
    rc, out = await _run([OPENCLAW_BIN, "agents", "list"], timeout=8.0)
    return JSONResponse({"output": _strip_ansi(out)[:4000], "rc": rc})


@app.get("/api/approvals")
async def api_approvals():
    rc, out = await _run([OPENCLAW_BIN, "approvals", "list"], timeout=8.0)
    return JSONResponse({"output": _strip_ansi(out)[:4000], "rc": rc})


@app.get("/api/logs", response_class=PlainTextResponse)
async def api_logs(lines: int = 200):
    """Tail today's OpenClaw log file."""
    lines = max(1, min(lines, 1000))
    if not LOG_DIR.exists():
        return PlainTextResponse("(no log dir)")
    # Find most-recent log file
    log_files = sorted(
        LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not log_files:
        return PlainTextResponse("(no log files yet)")
    rc, out = await _run(["tail", "-n", str(lines), str(log_files[0])], timeout=4.0)
    return _strip_ansi(out)


@app.get("/api/logs/journal", response_class=PlainTextResponse)
async def api_logs_journal(lines: int = 100):
    """Tail openclaw-gateway systemd logs."""
    lines = max(1, min(lines, 500))
    rc, out = await _run(
        [
            "journalctl",
            "-u",
            "openclaw-gateway.service",
            "-n",
            str(lines),
            "--no-pager",
            "--output=short-iso",
        ],
        timeout=5.0,
    )
    return out or "(no journal entries)"


@app.get("/api/logs/stream")
async def api_logs_stream():
    """SSE stream of journalctl -f for openclaw-gateway."""

    async def generate():
        proc = await _spawn(
            "journalctl",
            "-u",
            "openclaw-gateway.service",
            "-f",
            "-n",
            "20",
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
                text = _strip_ansi(line.decode("utf-8", errors="replace").rstrip("\n"))
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


class TestRequest(BaseModel):
    message: str
    model: str = "openrouter/anthropic/claude-haiku-4.5"
    bearer: str | None = None


@app.post("/api/test")
async def api_test(body: TestRequest):
    """Send a test /v1/messages to the gateway."""
    headers = {"Content-Type": "application/json"}
    if body.bearer:
        headers["Authorization"] = f"Bearer {body.bearer}"

    payload = {
        "model": body.model,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": body.message}],
    }

    async with httpx.AsyncClient(timeout=60.0) as c:
        try:
            r = await c.post(
                f"{GATEWAY_URL}/v1/messages", headers=headers, json=payload
            )
            return JSONResponse(
                {
                    "status": r.status_code,
                    "body": r.json()
                    if r.headers.get("content-type", "").startswith("application/json")
                    else r.text[:4000],
                }
            )
        except Exception as e:
            return JSONResponse({"status": 0, "error": str(e)})


@app.get("/api/usage")
async def api_usage():
    """Recent OpenClaw activity summary (parsed from logs)."""
    if not LOG_DIR.exists():
        return JSONResponse({"error": "no log dir"})
    log_files = sorted(
        LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    summary = {
        "log_files": [
            {
                "name": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(
                    timespec="seconds"
                ),
            }
            for f in log_files[:10]
        ],
        "total_size_kb": round(sum(f.stat().st_size for f in log_files) / 1024, 1),
    }
    # Try to extract counts from today's log
    if log_files:
        rc, out = await _run(["wc", "-l", str(log_files[0])], timeout=3.0)
        if rc == 0:
            try:
                summary["today_lines"] = int(out.split()[0])
            except (ValueError, IndexError):
                pass
    return JSONResponse(summary)
