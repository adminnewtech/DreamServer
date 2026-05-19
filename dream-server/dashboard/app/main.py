"""Dream Dashboard - integrated VPS control center.

Pages:
  /            Services grid (default landing)
  /overview    KPI overview from all integrated systems
  /logs        Live log explorer with SSE streaming
  /metrics     Time-series charts (host + per-service)
  /databases   Postgres + Redis explorer
  /topology    Service dependency graph (SVG)
  /security    SSL certs + fail2ban + ports + processes
  /assistant   AI chat (uses 9Router)
  /auth/login  PIN login for write actions

API:
  GET  /api/health                  All service health
  GET  /api/system                  Host metrics snapshot
  GET  /api/metrics/host?hours=N    Host time-series
  GET  /api/metrics/service/{name}  Service time-series
  GET  /api/databases               PG + Redis info
  GET  /api/security                Certs + f2b + ports + procs
  GET  /api/integrations            Multica/Paperclip/Hermes/9R live KPIs
  GET  /api/topology                Graph nodes + edges
  GET  /logs/journal/{unit}         Static journal tail
  GET  /logs/docker/{container}     Docker logs tail
  GET  /logs/stream/{unit}          SSE stream (journalctl -f)
  GET  /logs/search?q=...           Cross-unit grep
  POST /actions/systemd/{unit}/{action}     restart|stop|start (PIN required)
  POST /actions/docker/{container}/{action} restart|stop|start (PIN required)
  POST /assistant/chat              Streaming AI chat (PIN required)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import BRAND_NAME, HOST_LABEL
from .routers import (
    actions,
    assistant,
    auth,
    databases,
    logs,
    metrics,
    overview,
    security,
    services,
    topology,
)
from . import sampler, storage

log = logging.getLogger("dream-dashboard")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

BASE = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    log.info("storage initialized")
    # Start background sampler
    task = asyncio.create_task(sampler.run_forever())
    log.info("metrics sampler started")
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=BRAND_NAME,
    description=f"Integrated VPS control center for {HOST_LABEL}",
    version="2.0.0",
    lifespan=lifespan,
)

# Templates with global helpers
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.globals["brand_name"] = BRAND_NAME
templates.env.globals["host_label"] = HOST_LABEL
app.state.templates = templates

# Static files (under /static)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

# Routers
app.include_router(services.router, tags=["services"])
app.include_router(overview.router, tags=["overview"])
app.include_router(logs.router, tags=["logs"])
app.include_router(metrics.router, tags=["metrics"])
app.include_router(databases.router, tags=["databases"])
app.include_router(topology.router, tags=["topology"])
app.include_router(security.router, tags=["security"])
app.include_router(assistant.router, tags=["assistant"])
app.include_router(auth.router, tags=["auth"])
app.include_router(actions.router, tags=["actions"])


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"


@app.get("/manifest.webmanifest")
async def pwa_manifest():
    """PWA manifest for installable dashboard."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {
            "name": BRAND_NAME,
            "short_name": "Dream",
            "description": "VPS service status board",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f0f13",
            "theme_color": "#9d00ff",
            "icons": [
                {"src": "/static/dream.svg", "sizes": "any", "type": "image/svg+xml"},
            ],
        }
    )


@app.get("/sw.js", response_class=PlainTextResponse)
async def service_worker():
    """Minimal SW for PWA install + offline shell."""
    return (
        "const C='dream-v2';\n"
        "self.addEventListener('install', e => self.skipWaiting());\n"
        "self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));\n"
        "self.addEventListener('fetch', e => {\n"
        "  if (e.request.method !== 'GET') return;\n"
        "  e.respondWith(\n"
        "    fetch(e.request).catch(() =>\n"
        "      caches.match(e.request).then(r => r || new Response('offline', {status: 503}))\n"
        "    )\n"
        "  );\n"
        "});\n"
    )
