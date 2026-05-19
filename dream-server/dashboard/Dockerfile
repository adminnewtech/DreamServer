FROM python:3.12-slim

# System tools needed for probes: systemctl, docker CLI, journalctl, pgrep
# Note: systemctl/journalctl access requires mounting the host's /run/systemd/system
# and using --pid=host, --privileged is NOT needed since we only read state.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl iproute2 procps \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI only (no daemon) - we'll mount /var/run/docker.sock
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DASHBOARD_SHOW_LOGINS=1

EXPOSE 9200

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:9200/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9200", "--proxy-headers"]
