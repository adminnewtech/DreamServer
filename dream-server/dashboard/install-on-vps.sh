#!/usr/bin/env bash
# Install Dream Dashboard natively on the VPS as a systemd service.
# Idempotent - safe to re-run.
set -euo pipefail

INSTALL_DIR=/opt/dream-dashboard
NGINX_HOST=dashboard.83-171-249-32.nip.io
PORT=9200

echo "==> Dream Dashboard installer"
echo "    Target: $INSTALL_DIR"
echo "    Port:   $PORT"
echo "    Host:   $NGINX_HOST"
echo

# 1. Ensure Python venv available
if ! command -v python3 >/dev/null; then
  echo "ERROR: python3 not installed"; exit 1
fi
if ! python3 -c "import venv" 2>/dev/null; then
  apt-get update && apt-get install -y python3-venv
fi

# 2. Stage files
SRC_DIR=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$INSTALL_DIR"
cp -r "$SRC_DIR/app" "$INSTALL_DIR/"
cp "$SRC_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SRC_DIR/dream-dashboard.service" "$INSTALL_DIR/"

# 3. Venv + deps
cd "$INSTALL_DIR"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip --quiet
.venv/bin/pip install -r requirements.txt --quiet

# 4. Install systemd unit
cp dream-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable dream-dashboard.service
systemctl restart dream-dashboard.service
sleep 2

# 5. Self-check
if curl -fsS http://127.0.0.1:$PORT/healthz >/dev/null; then
  echo "OK: dashboard healthy on 127.0.0.1:$PORT"
else
  echo "ERROR: dashboard not healthy"
  journalctl -u dream-dashboard.service -n 30 --no-pager
  exit 1
fi

# 6. nginx vhost
NGINX_CONF=/etc/nginx/sites-available/dream-dashboard
cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $NGINX_HOST;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $NGINX_HOST;

    # LE cert (run certbot first if missing)
    ssl_certificate     /etc/letsencrypt/live/$NGINX_HOST/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$NGINX_HOST/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    access_log /var/log/nginx/dream-dashboard.access.log;
    error_log  /var/log/nginx/dream-dashboard.error.log;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }
}
EOF

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/dream-dashboard

# 7. LE cert if missing
if [ ! -f /etc/letsencrypt/live/$NGINX_HOST/fullchain.pem ]; then
  echo "==> Requesting Let's Encrypt cert for $NGINX_HOST"
  # First switch nginx to HTTP-only for the challenge
  cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $NGINX_HOST;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 200 'pending cert'; }
}
EOF
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w /var/www/html -d $NGINX_HOST --non-interactive --agree-tos --email admin@newtechq8.com || {
    echo "WARN: cert issuance failed, leaving HTTP-only vhost"
  }
  # Restore full config
  cat > "$NGINX_CONF" <<EOF
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
    access_log /var/log/nginx/dream-dashboard.access.log;
    error_log  /var/log/nginx/dream-dashboard.error.log;
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 30s;
    }
}
EOF
fi

nginx -t && systemctl reload nginx

echo
echo "==> Done!"
echo "    https://$NGINX_HOST/"
echo "    journalctl -u dream-dashboard -f"
