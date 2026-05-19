#!/usr/bin/env bash
# Install OpenClaw Dashboard on the VPS - swaps the static landing for
# a full FastAPI dashboard, then rewires nginx to proxy openclaw.<host>
# to it (preserving direct gateway access via /healthz and /v1/*).
set -euo pipefail

INSTALL_DIR=/opt/openclaw-dashboard
PORT=9210
NGINX_HOST=openclaw.83-171-249-32.nip.io

echo "==> OpenClaw Dashboard installer"
echo "    Target: $INSTALL_DIR  · port $PORT"

SRC_DIR=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$INSTALL_DIR"

rm -rf "$INSTALL_DIR/app"
cp -r "$SRC_DIR/app" "$INSTALL_DIR/"
cp "$SRC_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SRC_DIR/openclaw-dashboard.service" "$INSTALL_DIR/"

# venv + deps
if [ ! -d "$INSTALL_DIR/.venv" ]; then
  python3 -m venv "$INSTALL_DIR/.venv"
fi
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet

# systemd
cp "$INSTALL_DIR/openclaw-dashboard.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable openclaw-dashboard.service
systemctl restart openclaw-dashboard.service
sleep 2

if curl -fsS http://127.0.0.1:$PORT/healthz >/dev/null; then
  echo "OK: dashboard healthy on 127.0.0.1:$PORT"
else
  echo "ERROR: dashboard not healthy"
  journalctl -u openclaw-dashboard.service -n 30 --no-pager
  exit 1
fi

# Update nginx vhost: /            -> dashboard
#                     /healthz     -> gateway probe
#                     /v1/         -> gateway API
#                     /auth/       -> auth endpoint
cat > /etc/nginx/sites-available/openclaw <<NGINXEOF
server {
    listen 80;
    server_name $NGINX_HOST;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name $NGINX_HOST;

    ssl_certificate     /etc/letsencrypt/live/$NGINX_HOST/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$NGINX_HOST/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    access_log /var/log/nginx/openclaw.access.log;
    error_log  /var/log/nginx/openclaw.error.log;

    # Dashboard at root (including /api/* and /static/*)
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_read_timeout 120s;
    }

    # Gateway healthz proxied directly (bypass dashboard for monitoring)
    location = /gateway-healthz {
        proxy_pass http://127.0.0.1:3080/healthz;
    }

    # Anthropic-compatible API direct passthrough
    location /v1/ {
        proxy_pass http://127.0.0.1:3080/v1/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_read_timeout 600s;
    }

    # SSE log stream needs no buffering
    location = /api/logs/stream {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 24h;
    }

    # Auth on 3082
    location /auth/ {
        proxy_pass http://127.0.0.1:3082/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF

nginx -t && systemctl reload nginx

echo
echo "==> Done!"
echo "    https://$NGINX_HOST/"
echo "    journalctl -u openclaw-dashboard -f"
