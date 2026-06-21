"""Central Dashboard configuratie.

Agent endpoints en security settings worden hier beheerd.
In productie: gebruik omgevingsvariabelen i.p.v. hardcoded values.
"""

import os

# ─── Agents (servers) ────────────────────────────────────────────────
AGENTS = {
    "umbrelos": {
        "name": "UmbrelOS",
        "url": os.getenv("AGENT_UMBRELOS_URL", "http://localhost:9100"),
        "api_key": os.getenv("AGENT_UMBRELOS_KEY", "dev-agent-key"),
    },
    "ubuntu": {
        "name": "Ubuntu Server",
        "url": os.getenv("AGENT_UBUNTU_URL", "http://localhost:9101"),
        "api_key": os.getenv("AGENT_UBUNTU_KEY", "dev-agent-key"),
    },
}

# ─── Security ────────────────────────────────────────────────────────
DASHBOARD_API_KEY = os.getenv("DASHBOARD_API_KEY", "dashboard-dev-key")
API_KEY_HEADER = "X-API-Key"

# ─── Server ──────────────────────────────────────────────────────────
HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.getenv("DASHBOARD_PORT", "8000"))
