# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ─── Runtime stage ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Docker CLI + curl voor healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Maak een niet-root user (moet wel in docker group zitten voor socket toegang)
RUN groupadd -r -g 999 docker 2>/dev/null || true; \
    groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -G docker -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

# Labels
LABEL org.opencontainers.image.title="Homelab Server Agent"
LABEL org.opencontainers.image.description="Server agent voor het Homelab Dashboard"
LABEL org.opencontainers.image.source="https://github.com/yero213/homelab-dashboard"
LABEL org.opencontainers.image.version="0.1.0"

EXPOSE 9100

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:9100/os || exit 1

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "9100"]
