"""Central configuration loaded from environment with sane defaults."""

from __future__ import annotations

import os
from pathlib import Path

# Paths
APP_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("DASHBOARD_DATA_DIR", "/opt/dream-dashboard/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DB = DATA_DIR / "metrics.sqlite"
AUDIT_DB = DATA_DIR / "audit.sqlite"

# Auth - PIN for write actions; blank means writes disabled in prod
ADMIN_PIN = os.environ.get("DASHBOARD_ADMIN_PIN", "")
SHOW_LOGINS = os.environ.get("DASHBOARD_SHOW_LOGINS", "1") == "1"

# Sampling
METRICS_SAMPLE_INTERVAL_S = int(os.environ.get("METRICS_SAMPLE_INTERVAL_S", "60"))
METRICS_RETENTION_HOURS = int(os.environ.get("METRICS_RETENTION_HOURS", "48"))

# Integrations
NINEROUTER_URL = os.environ.get(
    "NINEROUTER_URL", "https://9router.83-171-249-32.nip.io"
)
NINEROUTER_API_KEY = os.environ.get("NINEROUTER_API_KEY", "")
NINEROUTER_MODEL = os.environ.get("NINEROUTER_MODEL", "claude-sonnet-4-5")
MULTICA_MASTER_API = os.environ.get("MULTICA_MASTER_API", "http://127.0.0.1:9103")
PAPERCLIP_URL = os.environ.get("PAPERCLIP_URL", "http://127.0.0.1:3200")
HERMES_API = os.environ.get("HERMES_API", "http://127.0.0.1:8051")

# Databases
MULTICA_PG_DSN = os.environ.get(
    "MULTICA_PG_DSN", "postgresql://multica:multica123@127.0.0.1:5435/multica"
)
PAPERCLIP_PG_DSN = os.environ.get(
    "PAPERCLIP_PG_DSN", "postgresql://paperclip:paperclip@127.0.0.1:5433/paperclip"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# Branding
HOST_LABEL = os.environ.get("DASHBOARD_HOST_LABEL", "83.171.249.32")
BRAND_NAME = os.environ.get("DASHBOARD_BRAND", "Dream Dashboard")
