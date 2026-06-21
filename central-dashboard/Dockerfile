# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ─── Runtime stage ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# System dependencies voor healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Maak een niet-root user
RUN groupadd -r -g 1000 appuser && \
    useradd -r -u 1000 -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY ./app ./app

# Labels voor herkenbaarheid
LABEL org.opencontainers.image.title="Homelab Dashboard"
LABEL org.opencontainers.image.description="Central Web GUI voor homelab-serverbeheer"
LABEL org.opencontainers.image.source="https://github.com/yero213/homelab-dashboard"
LABEL org.opencontainers.image.version="0.1.0"

EXPOSE 8000

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
