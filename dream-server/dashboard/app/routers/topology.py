"""Topology page - SVG service dependency graph."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..health import probe_all
from ..services import GROUPS, all_services

router = APIRouter()


# Static dependency map: service_name -> [services it depends on]
DEPENDENCIES = {
    # Multica stack
    "Multica Frontend": ["Multica Backend", "nginx"],
    "Multica Backend": ["Multica Postgres", "Redis"],
    "C360 API": ["Multica Postgres"],
    "Inventory API": ["Multica Postgres"],
    "Master Dashboard API": ["Multica Postgres"],
    "Activity Feed API": ["Multica Postgres"],
    "RAG Search API": ["Multica Postgres"],
    "Federated Search API": ["Multica Postgres"],
    "Metrics API": ["Multica Postgres"],
    "Monitor API": ["Multica Postgres"],
    "Smart Workload Router": ["9Router"],
    "Agent Runtime Daemon": ["Anthropic Shim", "Multica Postgres"],
    "Usage Tail": ["Anthropic Shim", "Multica Postgres"],
    # Paperclip
    "Paperclip Server": ["Paperclip DB"],
    # Hermes
    "Hermes Workspace": ["Hermes WebUI", "9Router"],
    "Hermes WebUI": ["9Router"],
    "Hermes Workspace svc": ["9Router"],
    "Hermes Native Dashboard": ["9Router"],
    "Hermes Gateway": ["9Router"],
    "Hermes CDP Bridge": [],
    # Router stack
    "9Router": ["Anthropic Shim", "Ollama"],
    "Anthropic Shim": [],
    "Ollama": [],
    # MCP servers all depend on respective backends
    "GitHub MCP": [],
    "Hermes MCP": ["Hermes Workspace"],
    "Integrations MCP": ["Hermes Workspace"],
    "Postgres MCP": ["Multica Postgres"],
    "Search Tools MCP": [],
    "Shopify MCP": [],
    "Workspace MCP": [],
    "Workspace Stream MCP": [],
    "Zoho MCP": [],
    "gbrain HTTP MCP": ["Ollama"],
    # Infra
    "nginx": [],
    "Docker": [],
    "Redis": [],
    "Fail2Ban": [],
    "Multica Postgres": [],
    "Paperclip DB": [],
}


@router.get("/topology", response_class=HTMLResponse)
async def page_topology(request: Request):
    templates = request.app.state.templates
    services = await probe_all(all_services())
    status_by_name = {s["name"]: s["status"] for s in services}
    return templates.TemplateResponse(
        "pages/topology.html",
        {
            "request": request,
            "active_page": "topology",
            "groups": GROUPS,
            "status_by_name": status_by_name,
        },
    )


@router.get("/api/topology")
async def api_topology():
    services = await probe_all(all_services())
    status_by_name = {s["name"]: s["status"] for s in services}
    nodes = []
    edges = []
    for svc in services:
        nodes.append(
            {
                "id": svc["name"],
                "group": svc["group"],
                "group_label": svc["group_label"],
                "group_icon": svc["group_icon"],
                "status": svc["status"],
                "kind": svc["kind"],
            }
        )
        for dep in DEPENDENCIES.get(svc["name"], []):
            if dep in status_by_name:
                edges.append({"source": svc["name"], "target": dep})
    return JSONResponse({"nodes": nodes, "edges": edges})
