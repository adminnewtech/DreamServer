"""HTTP clients for existing services - hit /health endpoints and gather KPIs."""

from __future__ import annotations

import asyncio
import logging

import httpx

from ..config import NINEROUTER_URL, PAPERCLIP_URL

log = logging.getLogger("dream-dashboard.integrations")

_TIMEOUT = httpx.Timeout(connect=2.0, read=4.0, write=2.0, pool=2.0)


async def _safe_get_json(url: str, headers: dict | None = None) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, verify=False) as c:
            r = await c.get(url, headers=headers or {})
            if r.status_code >= 400:
                return None
            try:
                return r.json()
            except Exception:
                return None
    except Exception:
        return None


async def multica_kpis() -> dict:
    """Aggregate KPIs from multiple Multica APIs."""
    endpoints = [
        ("master", "http://127.0.0.1:9103/health"),
        ("c360", "http://127.0.0.1:9062/health"),
        ("inventory", "http://127.0.0.1:9063/health"),
        ("shopify", "http://127.0.0.1:8063/health"),
        ("model", "http://127.0.0.1:8060/health"),
    ]
    results = await asyncio.gather(
        *[_safe_get_json(url) for _, url in endpoints], return_exceptions=True
    )

    out: dict = {}
    healthy = 0
    for (name, _), r in zip(endpoints, results):
        if isinstance(r, dict):
            healthy += 1
            if name == "c360" and "unified_customers" in r:
                out["unified customers"] = f"{r['unified_customers']:,}"
            elif name == "shopify":
                if "shop_name" in r:
                    out["shop"] = r["shop_name"]
                if "domain" in r:
                    out["domain"] = r["domain"]
            elif name == "model" and "model_default" in r:
                out["default model"] = r["model_default"]

    out["APIs healthy"] = f"{healthy}/{len(endpoints)}"
    if not out or healthy == 0:
        return {"_error": "No multica APIs responding"}
    return out


async def paperclip_health() -> dict:
    r = await _safe_get_json(f"{PAPERCLIP_URL}/api/health")
    if not r:
        return {"_error": "no response"}
    out = {}
    for k in ("status", "deploymentMode", "bootstrapStatus"):
        if k in r:
            out[k] = r[k]
    out["health URL"] = f"{PAPERCLIP_URL}/api/health"
    return out


async def hermes_status() -> dict:
    r = await _safe_get_json("http://127.0.0.1:8061/health")
    if not r:
        return {"_error": "no response"}
    out = {"status": r.get("status", "?")}
    version = r.get("version", "")
    if version:
        # Trim multi-line version string to first line
        out["version"] = version.split("\n")[0][:60]
    return out


async def ninerouter_stats() -> dict:
    health = await _safe_get_json(f"{NINEROUTER_URL.rstrip('/')}/api/health")
    if not health:
        return {"_error": "no response"}
    out = {"status": "ok" if health.get("ok") else "degraded"}
    # Try to get usage stats if exposed
    stats = await _safe_get_json(f"{NINEROUTER_URL.rstrip('/')}/api/stats")
    if isinstance(stats, dict):
        for k in ("requests_today", "tokens_today", "model_distribution"):
            if k in stats:
                out[k] = stats[k]
    return out


async def gather_all() -> dict:
    keys = ["multica", "paperclip", "hermes", "ninerouter"]
    results = await asyncio.gather(
        multica_kpis(),
        paperclip_health(),
        hermes_status(),
        ninerouter_stats(),
        return_exceptions=True,
    )
    out: dict = {}
    for k, r in zip(keys, results):
        if isinstance(r, Exception):
            out[k] = {"_error": str(r)[:200]}
        elif isinstance(r, dict):
            out[k] = r
        else:
            out[k] = {"_error": "unexpected response"}
    return out
