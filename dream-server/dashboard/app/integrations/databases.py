"""Postgres + Redis read-only inspectors."""

from __future__ import annotations

import asyncio
import logging

from ..config import MULTICA_PG_DSN, PAPERCLIP_PG_DSN, REDIS_URL

log = logging.getLogger("dream-dashboard.databases")


async def _pg_inspect(dsn: str, label: str) -> dict:
    """Connect to PG, return DB list + top tables by size."""
    try:
        import asyncpg  # type: ignore
    except ImportError:
        return {"label": label, "error": "asyncpg not installed"}

    try:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=3.0)
    except Exception as e:
        return {"label": label, "error": f"connect: {str(e)[:120]}"}

    try:
        version = await conn.fetchval("SELECT version()")
        db_size = await conn.fetchval(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )
        table_count = await conn.fetchval(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )
        top_tables = await conn.fetch(
            """
            SELECT c.relname AS name,
                   COALESCE(s.n_live_tup, 0) AS rows,
                   pg_size_pretty(pg_total_relation_size(c.oid)) AS size
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
            LIMIT 15
            """
        )
        return {
            "label": label,
            "version": (version or "").split(" on ")[0],
            "db_size": db_size,
            "table_count": table_count,
            "top_tables": [
                {"name": r["name"], "rows": r["rows"], "size": r["size"]}
                for r in top_tables
            ],
        }
    except Exception as e:
        return {"label": label, "error": str(e)[:200]}
    finally:
        await conn.close()


async def _redis_inspect() -> dict:
    try:
        import redis.asyncio as redis  # type: ignore
    except ImportError:
        return {"error": "redis not installed"}

    try:
        client = redis.from_url(REDIS_URL, socket_timeout=2.0)
        info = await client.info()
        dbsize = await client.dbsize()
        await client.aclose()
        return {
            "version": info.get("redis_version"),
            "uptime_h": round(info.get("uptime_in_seconds", 0) / 3600, 1),
            "used_memory": info.get("used_memory_human"),
            "connected_clients": info.get("connected_clients"),
            "total_commands": info.get("total_commands_processed"),
            "ops_per_sec": info.get("instantaneous_ops_per_sec"),
            "keys": dbsize,
        }
    except Exception as e:
        return {"error": str(e)[:200]}


async def inspect_all() -> dict:
    multica, paperclip, redis_info = await asyncio.gather(
        _pg_inspect(MULTICA_PG_DSN, "Multica"),
        _pg_inspect(PAPERCLIP_PG_DSN, "Paperclip"),
        _redis_inspect(),
        return_exceptions=True,
    )
    return {
        "postgres": [
            multica
            if not isinstance(multica, Exception)
            else {"label": "Multica", "error": str(multica)},
            paperclip
            if not isinstance(paperclip, Exception)
            else {"label": "Paperclip", "error": str(paperclip)},
        ],
        "redis": redis_info
        if not isinstance(redis_info, Exception)
        else {"error": str(redis_info)},
    }
