# Homelab Dashboard

Centrale Web GUI om je homelab-omgeving te beheren.  
Gebouwd met **FastAPI** (backend) en **TailwindCSS** (frontend).

## Architectuur

                    ┌───────────────────────┐
                    │   Central Dashboard   │
                    │   (FastAPI + UI)      │
                    │   localhost:8000       │
                    └───────┬───────┬───────┘
                            │       │
                  ┌─────────┘       └─────────┐
                  ▼                             ▼
        ┌──────────────────┐     ┌──────────────────┐
        │  Agent UmbrelOS  │     │  Agent Ubuntu     │
        │  :9100           │     │  :9101            │
        │  (Docker)        │     │  (systemd/Docker) │
        └──────────────────┘     └──────────────────┘

### Components

| Component | Tech | Rol |
|-----------|------|-----|
| **Central Dashboard** | FastAPI + TailwindCSS | Web UI met tabs per server, API-proxy naar agents |
| **Server Agent** | FastAPI + psutil + docker-py | Draait op elke server, verzamelt metrics en beheert Docker |

## Setup

### 1. Lokaal (development)

```bash
# Dashboard
cd central-dashboard
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Agent (in een andere terminal)
cd server-agent
pip install -r requirements.txt
uvicorn agent:app --reload --port 9100
```

### 2. Met Docker Compose

```bash
docker compose up --build
```

Open **http://localhost:8000** in je browser.

### 3. Ubuntu Server — Agent als systemd-service

```bash
# Op de Ubuntu-machine
sudo apt install python3-pip
git clone <deze-repo> /opt/homelab-agent
cd /opt/homelab-agent/server-agent
pip install -r requirements.txt

# Maak een systemd-service aan
sudo tee /etc/systemd/system/homelab-agent.service > /dev/null <<EOF
[Unit]
Description=Homelab Server Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m uvicorn agent:app --host 0.0.0.0 --port 9100
WorkingDirectory=/opt/homelab-agent/server-agent
Environment=AGENT_API_KEY=prod-agent-key
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now homelab-agent
```

## API Endpoints

### Dashboard API (beveiligd met `X-API-Key`)

| Methode | Pad | Beschrijving |
|---------|-----|-------------|
| GET | `/api/servers/` | Lijst servers |
| GET | `/api/servers/{id}/overview` | Volledig overzicht |
| GET | `/api/servers/{id}/os` | OS-info |
| GET | `/api/servers/{id}/storage` | Opslag |
| GET | `/api/servers/{id}/hardware` | CPU/RAM |
| GET | `/api/servers/{id}/docker` | Docker containers |
| POST | `/api/servers/{id}/docker/{cid}/{action}` | Start/stop/restart |

### Agent API (beveiligd met `X-API-Key`)

| Methode | Pad | Beschrijving |
|---------|-----|-------------|
| GET | `/overview` | Alles |
| GET | `/os` | OS-info |
| GET | `/storage` | Schijfruimte |
| GET | `/hardware` | CPU/RAM |
| GET | `/docker` | Docker containers |
| POST | `/docker/{id}/{action}` | Container actie |

## Volgende stappen (todo)

- [ ] Echte authenticatie (JWT / session-based)
- [ ] Grafieken voor historische metrics (via Chart.js of similar)
- [ ] Notificaties bij problemen (disk vol, container gecrasht)
- [ ] Donkere/lichte modus toggle
- [ ] Multi-user ondersteuning
