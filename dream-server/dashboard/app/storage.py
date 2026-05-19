"""SQLite storage for metrics + audit log.

Tables:
  host_metrics(ts, cpu_pct, load1, mem_pct, mem_total_gb, disk_pct)
  service_metrics(ts, name, status, cpu_pct, mem_mb)
  audit_log(ts, actor, action, target, result, detail)
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterable

from .config import AUDIT_DB, METRICS_DB, METRICS_RETENTION_HOURS


@contextmanager
def _conn(path):
    con = sqlite3.connect(str(path), timeout=10)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn(METRICS_DB) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS host_metrics (
                ts           INTEGER NOT NULL,
                cpu_pct      REAL,
                load1        REAL,
                mem_pct      REAL,
                mem_total_gb REAL,
                disk_pct     REAL
            );
            CREATE INDEX IF NOT EXISTS idx_host_ts ON host_metrics(ts);

            CREATE TABLE IF NOT EXISTS service_metrics (
                ts     INTEGER NOT NULL,
                name   TEXT NOT NULL,
                status TEXT,
                cpu_pct REAL,
                mem_mb REAL
            );
            CREATE INDEX IF NOT EXISTS idx_svc_ts_name ON service_metrics(ts, name);
            CREATE INDEX IF NOT EXISTS idx_svc_name ON service_metrics(name);
            """
        )
    with _conn(AUDIT_DB) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                ts     INTEGER NOT NULL,
                actor  TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                result TEXT,
                detail TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
            """
        )


def write_host_sample(sample: dict) -> None:
    with _conn(METRICS_DB) as c:
        c.execute(
            "INSERT INTO host_metrics(ts, cpu_pct, load1, mem_pct, mem_total_gb, disk_pct) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                int(time.time()),
                sample.get("cpu_pct"),
                sample.get("load1"),
                sample.get("mem_pct"),
                sample.get("mem_total_gb"),
                sample.get("disk_pct"),
            ),
        )


def write_service_samples(samples: Iterable[dict]) -> None:
    rows = [
        (
            int(time.time()),
            s["name"],
            s.get("status"),
            s.get("cpu_pct"),
            s.get("mem_mb"),
        )
        for s in samples
    ]
    if not rows:
        return
    with _conn(METRICS_DB) as c:
        c.executemany(
            "INSERT INTO service_metrics(ts, name, status, cpu_pct, mem_mb) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )


def host_history(hours: int = 24) -> list[dict]:
    cutoff = int(time.time()) - hours * 3600
    with _conn(METRICS_DB) as c:
        rows = c.execute(
            "SELECT ts, cpu_pct, load1, mem_pct, disk_pct FROM host_metrics "
            "WHERE ts >= ? ORDER BY ts ASC",
            (cutoff,),
        ).fetchall()
    return [
        {"ts": r[0], "cpu_pct": r[1], "load1": r[2], "mem_pct": r[3], "disk_pct": r[4]}
        for r in rows
    ]


def service_history(name: str, hours: int = 24) -> list[dict]:
    cutoff = int(time.time()) - hours * 3600
    with _conn(METRICS_DB) as c:
        rows = c.execute(
            "SELECT ts, status, cpu_pct, mem_mb FROM service_metrics "
            "WHERE name=? AND ts>=? ORDER BY ts ASC",
            (name, cutoff),
        ).fetchall()
    return [{"ts": r[0], "status": r[1], "cpu_pct": r[2], "mem_mb": r[3]} for r in rows]


def prune() -> None:
    cutoff = int(time.time()) - METRICS_RETENTION_HOURS * 3600
    with _conn(METRICS_DB) as c:
        c.execute("DELETE FROM host_metrics WHERE ts < ?", (cutoff,))
        c.execute("DELETE FROM service_metrics WHERE ts < ?", (cutoff,))


def audit(
    actor: str,
    action: str,
    target: str | None = None,
    result: str = "ok",
    detail: str = "",
) -> None:
    with _conn(AUDIT_DB) as c:
        c.execute(
            "INSERT INTO audit_log(ts, actor, action, target, result, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (int(time.time()), actor, action, target, result, detail[:500]),
        )


def audit_recent(limit: int = 50) -> list[dict]:
    with _conn(AUDIT_DB) as c:
        rows = c.execute(
            "SELECT ts, actor, action, target, result, detail FROM audit_log "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "ts": r[0],
            "actor": r[1],
            "action": r[2],
            "target": r[3],
            "result": r[4],
            "detail": r[5],
        }
        for r in rows
    ]
