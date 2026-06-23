# ═══════════════════════════════════════════════════════════════════
#  Homelab Dashboard — Server Agent Dockerfile
# ═══════════════════════════════════════════════════════════════════
#  Lichtgewicht Python container voor de server-agent.
#  Draait op elke Linux-server en verzamelt systeemdata.
#
#  Vereist bij opstarten:
#   - .env bestand met AGENT_API_KEY
#   - /var/run/docker.sock (voor Docker container management)
#   - /host/proc (voor hostnaam detectie in Docker)
#   - /host/etc (voor OS-detectie in Docker)
# ═══════════════════════════════════════════════════════════════════

FROM python:3.13-slim

# ─── Systeem dependencies ─────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ─── Applicatie directory ─────────────────────────────────────────
WORKDIR /app

# ─── Python dependencies ─────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Applicatie code ─────────────────────────────────────────────
COPY . .

# ─── Niet-root gebruiker ─────────────────────────────────────────
RUN addgroup --system app && \
    adduser --system --ingroup app app && \
    chown -R app:app /app

USER app

# ─── Container config ────────────────────────────────────────────
EXPOSE 9100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9100/health')" || exit 1

CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "9100"]
