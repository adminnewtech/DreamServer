"""AI Server Assistant - wraps 9Router (OpenAI-compatible) with server context."""

from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx

from ..config import NINEROUTER_API_KEY, NINEROUTER_MODEL, NINEROUTER_URL
from ..health import probe_all, system_summary
from ..services import all_services

log = logging.getLogger("dream-dashboard.assistant")

SYSTEM_PROMPT = """You are the AI assistant for the Newtech VPS Dream Dashboard.
You help the operator understand and troubleshoot 41 services across these groups:
- Multica Dashboard (16 services - APIs, frontend, agent daemon, RAG, search)
- Paperclip Business (Paperclip server + PG)
- Hermes Agent (workspace, webui, gateway, CDP bridge)
- 9Router + LLM (smart LLM routing, anthropic shim, ollama)
- MCP Servers (10 MCP servers for GitHub, Hermes, Postgres, Shopify, Zoho, etc.)
- Infrastructure (nginx, Docker, Redis, Fail2Ban)

You have access to live service status, host metrics, and you can suggest commands
the operator should run (but you cannot execute them). Be concise. Use the live
status snapshot at the top of each message. Respond in the user's language
(Arabic or English). Format response in markdown."""


async def _live_context() -> str:
    """Build a compact text snapshot of server state to inject as context."""
    services = await probe_all(all_services())
    summary = await system_summary()

    by_status: dict[str, list[str]] = {}
    for s in services:
        by_status.setdefault(s["status"], []).append(s["name"])

    lines = [
        "## Live Status Snapshot",
        f"Host: 83.171.249.32 | uptime {summary.get('uptime_h')}h | "
        f"load {summary.get('load')} | mem {summary.get('mem_used_pct')}% "
        f"of {summary.get('mem_total_gb')}G | disk {summary.get('disk_used_pct')}",
        "",
    ]
    for status, names in by_status.items():
        lines.append(
            f"- **{status}** ({len(names)}): {', '.join(names[:8])}{'...' if len(names) > 8 else ''}"
        )

    # Add detail for any non-up services
    bad = [s for s in services if s["status"] not in ("up",)]
    if bad:
        lines.append("\n### Non-healthy details")
        for s in bad[:8]:
            lines.append(
                f"- {s['name']} ({s['kind']}) -> {s['status']}: {s.get('detail', '')[:140]}"
            )
    return "\n".join(lines)


async def chat_stream(user_message: str) -> AsyncIterator[str]:
    """Stream tokens from 9Router. Yields plain text chunks."""
    context = await _live_context()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context},
        {"role": "user", "content": user_message},
    ]

    headers = {"Content-Type": "application/json"}
    if NINEROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {NINEROUTER_API_KEY}"

    payload = {
        "model": NINEROUTER_MODEL,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
    }

    url = f"{NINEROUTER_URL.rstrip('/')}/v1/chat/completions"

    timeout = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            async with client.stream(
                "POST", url, headers=headers, json=payload
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    yield f"\n\n_9Router error: HTTP {resp.status_code} - {body.decode('utf-8', errors='replace')[:200]}_"
                    return
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        import json

                        chunk = json.loads(data)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            yield delta
                    except Exception:
                        continue
    except Exception as e:
        yield f"\n\n_Assistant error: {str(e)[:200]}_"
