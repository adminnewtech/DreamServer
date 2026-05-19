# Dream Dashboard

A live status board for every service running on the Newtech VPS — built on the DreamServer fork.

![Dream Dashboard preview](docs/preview.png)

## What it shows

- **40+ services across 6 groups:** Multica, Paperclip, Hermes, 9Router, MCP servers, Infrastructure
- **Live health** via systemctl/docker/HTTP/TCP probes (cached 8s, refreshed every 10s)
- **Login reference table** — quick lookup for URLs, users, ports
- **Host metrics** — uptime, load, memory, disk
- **Per-service logs** — one click to see last 50 journal lines

## Install on the VPS

```bash
scp -r dashboard root@83.171.249.32:/tmp/
ssh root@83.171.249.32 'cd /tmp/dashboard && bash install-on-vps.sh'
```

After install:
- **URL:** https://dashboard.83-171-249-32.nip.io/
- **systemd:** `systemctl status dream-dashboard`
- **logs:** `journalctl -u dream-dashboard -f`

## Architecture

```
Browser → nginx (443) → uvicorn (127.0.0.1:9200) → app.main:app
                                                    │
                                                    ├── systemctl is-active <unit>
                                                    ├── docker inspect <container>
                                                    ├── httpx.AsyncClient.get(url)
                                                    ├── socket.create_connection(host, port)
                                                    └── pgrep -f <name>
```

- **FastAPI + Jinja2 + HTMX** — no JS framework, server-rendered partials, 10s auto-refresh
- **Native install (not Docker)** — needs direct access to systemctl/journalctl/docker
- **Concurrent probes** via `asyncio.gather` — full status in <1s
- **In-process LRU cache** (8s TTL) — keeps load light

## Adding services

Edit `app/services.py`. Each entry needs:
- `kind`: `systemd` | `docker` | `http` | `process` | `pg` | `redis`
- `unit` / `container` / `url` / `process` based on kind
- `port`, `url`, `desc` for display

Restart: `systemctl restart dream-dashboard`.

## API

| Route | Returns |
|-------|---------|
| `GET /` | Full HTML dashboard |
| `GET /partial/grid` | HTML fragment (HTMX target) |
| `GET /api/health` | JSON array of all services with status |
| `GET /api/system` | JSON host metrics |
| `GET /logs/<unit>` | Last 50 journal lines (plain text) |
| `GET /healthz` | `ok` (self health-check) |

## Security

- `127.0.0.1` bind only — nginx terminates TLS and forwards
- `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome` in systemd unit
- `DASHBOARD_SHOW_LOGINS=0` to hide the access reference table
- No write access to the system — only reads `systemctl is-active` and `docker inspect`
