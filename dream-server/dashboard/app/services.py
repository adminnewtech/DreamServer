"""Service registry — single source of truth for what runs on the VPS.

Grouped by domain. Each entry has:
  - name: human label
  - port: TCP port on host (None for unix/internal)
  - kind: 'http' | 'systemd' | 'docker' | 'pg' | 'redis'
  - url: public URL (None for internal)
  - login: login hints/URL (None for open)
  - desc: 1-line description
  - check: how to verify it's alive
"""

from __future__ import annotations

GROUPS: dict[str, dict] = {
    "multica": {
        "label": "Multica Dashboard",
        "icon": "📊",
        "color": "#3b82f6",
        "services": [
            {
                "name": "Multica Frontend",
                "port": 3002,
                "kind": "docker",
                "url": "https://multica.83-171-249-32.nip.io/",
                "container": "multica-frontend-1",
                "desc": "React UI for Multica",
            },
            {
                "name": "Multica Backend",
                "port": 8080,
                "kind": "docker",
                "url": "https://multica.83-171-249-32.nip.io/api/",
                "container": "multica-backend-1",
                "desc": "Core API",
            },
            {
                "name": "Multica Postgres",
                "port": 5435,
                "kind": "docker",
                "url": None,
                "container": "multica-postgres-1",
                "desc": "PostgreSQL (multica/multica123)",
            },
            {
                "name": "C360 API",
                "port": 9062,
                "kind": "systemd",
                "url": "https://multica.83-171-249-32.nip.io/api/c360/health",
                "unit": "multica-c360.service",
                "desc": "Customer 360 analytics",
            },
            {
                "name": "Inventory API",
                "port": 9063,
                "kind": "systemd",
                "url": "https://multica.83-171-249-32.nip.io/api/inv/",
                "unit": "multica-inv.service",
                "desc": "Inventory analytics",
            },
            {
                "name": "Master Dashboard API",
                "port": 9103,
                "kind": "systemd",
                "url": None,
                "unit": "multica-master-api.service",
                "desc": "Master dashboard backend",
            },
            {
                "name": "Activity Feed API",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-activity-feed.service",
                "desc": "Event stream",
            },
            {
                "name": "Federated Search API",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-federated-search.service",
                "desc": "Cross-source search",
            },
            {
                "name": "RAG Search API",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-rag.service",
                "desc": "RAG retrieval",
            },
            {
                "name": "Metrics API",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-metrics-api.service",
                "desc": "Metrics endpoint",
            },
            {
                "name": "Monitor API",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-monitor.service",
                "desc": "Health monitor",
            },
            {
                "name": "Smart Workload Router",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-smart-router-webhook.service",
                "desc": "AI workload routing",
            },
            {
                "name": "Agent Runtime Daemon",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-daemon.service",
                "desc": "Agent runtime",
            },
            {
                "name": "GitHub Webhook",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-github-webhook.service",
                "desc": "GitHub event bridge",
            },
            {
                "name": "Webhook Refresh Trigger",
                "port": 9099,
                "kind": "systemd",
                "url": None,
                "unit": "multica-webhook-refresh-trigger.service",
                "desc": "Refresh trigger",
            },
            {
                "name": "Usage Tail",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "multica-usage-tail.service",
                "desc": "anthropic-shim usage logger",
            },
        ],
    },
    "paperclip": {
        "label": "Paperclip Business",
        "icon": "📎",
        "color": "#8b5cf6",
        "services": [
            {
                "name": "Paperclip Server",
                "port": 3200,
                "kind": "docker",
                "url": "http://83.171.249.32:3200/",
                "container": "paperclip-biz-server-1",
                "desc": "Paperclip Business UI + API",
            },
            {
                "name": "Paperclip DB",
                "port": 5433,
                "kind": "docker",
                "url": None,
                "container": "paperclip-biz-db-1",
                "desc": "PostgreSQL for Paperclip",
            },
        ],
    },
    "hermes": {
        "label": "Hermes Agent",
        "icon": "🚀",
        "color": "#ec4899",
        "services": [
            {
                "name": "Hermes Workspace",
                "port": None,
                "kind": "docker",
                "url": "https://workspace.83-171-249-32.nip.io/",
                "container": "hermes-workspace-jadeed",
                "desc": "Web workspace UI",
            },
            {
                "name": "Hermes WebUI",
                "port": None,
                "kind": "systemd",
                "url": "https://hermes.83-171-249-32.nip.io/",
                "unit": "hermes-webui.service",
                "desc": "Browser interface",
            },
            {
                "name": "Hermes Workspace svc",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "hermes-workspace.service",
                "desc": "Workspace systemd unit",
            },
            {
                "name": "Hermes Native Dashboard",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "hermes-dashboard-native.service",
                "desc": "Native dashboard",
            },
            {
                "name": "Hermes Gateway",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "hermes-gateway.service",
                "desc": "Messaging gateway",
            },
            {
                "name": "Hermes CDP Bridge",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "hermes-cdp-bridge.service",
                "desc": "Chrome DevTools proxy",
            },
        ],
    },
    "router": {
        "label": "9Router + LLM",
        "icon": "🧠",
        "color": "#10b981",
        "services": [
            {
                "name": "9Router",
                "port": 20128,
                "kind": "systemd",
                "url": "https://9router.83-171-249-32.nip.io/login",
                "unit": "9router.service",
                "desc": "Smart LLM routing (7 combos)",
            },
            {
                "name": "Anthropic Shim",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "anthropic-shim.service",
                "desc": "Claude Max via CLI shim",
            },
            {
                "name": "Ollama",
                "port": 11434,
                "kind": "process",
                "url": None,
                "process": "ollama",
                "desc": "Local Ollama (nomic-embed)",
            },
        ],
    },
    "mcp": {
        "label": "MCP Servers",
        "icon": "🔌",
        "color": "#f59e0b",
        "services": [
            {
                "name": "GitHub MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-github.service",
                "desc": "gh CLI wrapper (SSE)",
            },
            {
                "name": "Hermes MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-hermes.service",
                "desc": "Hermes Agent MCP",
            },
            {
                "name": "Integrations MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-integrations.service",
                "desc": "Hermes+OpenClaw+Shopify+Zoho+Search",
            },
            {
                "name": "Postgres MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-postgres.service",
                "desc": "Read-only PG access",
            },
            {
                "name": "Search Tools MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-search-tools.service",
                "desc": "DuckDuckGo+Jina+Brave+Firecrawl",
            },
            {
                "name": "Shopify MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-shopify.service",
                "desc": "Read-only Shopify for Newtechkw",
            },
            {
                "name": "Workspace MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-workspace.service",
                "desc": "FS + git access",
            },
            {
                "name": "Workspace Stream MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-workspace-stream.service",
                "desc": "Streamable HTTP variant",
            },
            {
                "name": "Zoho MCP",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "mcp-zoho.service",
                "desc": "Read-only Zoho for Newtechkw",
            },
            {
                "name": "gbrain HTTP MCP",
                "port": 3132,
                "kind": "systemd",
                "url": "https://gbrain.83-171-249-32.nip.io/",
                "unit": "gbrain.service",
                "desc": "Knowledge graph MCP",
            },
        ],
    },
    "infra": {
        "label": "Infrastructure",
        "icon": "⚙️",
        "color": "#6b7280",
        "services": [
            {
                "name": "nginx",
                "port": 443,
                "kind": "systemd",
                "url": "https://multica.83-171-249-32.nip.io/",
                "unit": "nginx.service",
                "desc": "Reverse proxy + LE certs",
            },
            {
                "name": "Docker",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "docker.service",
                "desc": "Container runtime",
            },
            {
                "name": "Redis",
                "port": 6379,
                "kind": "docker",
                "url": None,
                "container": "md-redis",
                "desc": "Cache/queue",
            },
            {
                "name": "Fail2Ban",
                "port": None,
                "kind": "systemd",
                "url": None,
                "unit": "fail2ban.service",
                "desc": "SSH brute-force protection",
            },
        ],
    },
}

# Login info — separate to allow easier redaction / role-based reveal.
LOGINS = {
    "Multica Frontend": {
        "url": "https://multica.83-171-249-32.nip.io/",
        "user": "admin",
        "notes": "Multica admin (see vault for password)",
    },
    "Multica Postgres": {
        "host": "127.0.0.1:5435",
        "user": "multica",
        "db": "multica",
        "pass": "multica123",
    },
    "Paperclip DB": {"host": "0.0.0.0:5433", "user": "see Paperclip env"},
    "Paperclip Server": {
        "url": "http://83.171.249.32:3200/",
        "user": "first-run signup",
    },
    "Hermes Workspace": {
        "url": "https://workspace.83-171-249-32.nip.io/",
        "user": "Hermes built-in auth",
    },
    "Hermes WebUI": {
        "url": "https://hermes.83-171-249-32.nip.io/",
        "user": "Hermes built-in auth",
    },
    "9Router": {
        "url": "https://9router.83-171-249-32.nip.io/login",
        "user": "see 9router .env",
    },
    "gbrain HTTP MCP": {
        "url": "https://gbrain.83-171-249-32.nip.io/",
        "user": "MCP token auth",
    },
}


def all_services() -> list[dict]:
    out = []
    for gid, g in GROUPS.items():
        for s in g["services"]:
            out.append(
                {
                    **s,
                    "group": gid,
                    "group_label": g["label"],
                    "group_color": g["color"],
                    "group_icon": g["icon"],
                }
            )
    return out
