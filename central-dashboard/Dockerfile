# ═══════════════════════════════════════════════════════════════════
#  Homelab Dashboard — Centraal Dashboard Dockerfile
# ═══════════════════════════════════════════════════════════════════
#  Lichtgewicht Python container voor het centrale dashboard.
#  Serveert de frontend en proxied requests naar server-agents.
#
#  Vereist bij opstarten:
#   - .env bestand met DASHBOARD_API_KEY
#   - Agent configuraties in .env (AGENT_<ID>_URL, AGENT_<ID>_KEY)
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
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
