# Homelab Dashboard

Central web GUI for managing a homelab with multiple Linux servers. Monochrome, editorial design — fast, touch-optimized, self-hosted.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Central Dashboard                     │
│                   (FastAPI · port 8000)                  │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Frontend │  │   API    │  │ Services │  │ Models │ │
│  │ (static) │  │  Router  │  │ (httpx)  │  │(Pydantic)
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌──────────┐  ┌──────────┐
   │  Agent   │  │  Agent   │
   │ UmbrelOS │  │  Ubuntu  │
   │ :9100    │  │ :9101    │
   └──────────┘  └──────────┘
```

### Components

| Component | Technology | Port | Description |
|-----------|-----------|------|-------------|
| **Central Dashboard** | FastAPI + Uvicorn | 8000 | Serves the frontend and proxies API requests to agents |
| **Server Agent** | FastAPI + Uvicorn | 9100 | Collects OS, hardware, storage, and Docker data |
| **Frontend** | Vanilla JS + CSS | — | Monochrome editorial UI, served by the dashboard |

### Server Agent Endpoints

All endpoints (except `/health`) require `X-API-Key` header.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (no auth required) |
| `/os` | GET | Hostname, OS type, kernel, uptime |
| `/hardware` | GET | CPU%, CPU cores, RAM usage |
| `/storage` | GET | Disk storage per mount point |
| `/containers` | GET | Docker containers list |
| `/containers/{id}/{action}` | POST | Start/stop/restart a container |
| `/overview` | GET | All metrics combined |
| `/metrics` | GET | Alias for `/overview` |

### Dashboard API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/servers` | GET | List configured servers |
| `/api/servers/{id}/overview` | GET | Full data for one server |
| `/api/servers/{id}/os` | GET | OS info for one server |
| `/api/servers/{id}/hardware` | GET | Hardware metrics for one server |
| `/api/servers/{id}/storage` | GET | Storage info for one server |
| `/api/servers/{id}/containers` | GET | Containers for one server |
| `/api/servers/{id}/containers/{cid}/{action}` | POST | Container action (requires API key) |
| `/api/dashboard` | GET | Aggregated data from all servers |

**Auth**: GET endpoints are freely accessible from the frontend. POST endpoints require `X-API-Key` header.

## Quick Start

### Prerequisites

- Python 3.13+
- Linux server (tested on Arch Linux, Ubuntu Server, UmbrelOS)
- Docker (optional — for container management)

### 1. Clone & Setup

```bash
git clone <repo-url> homelab-dashboard
cd homelab-dashboard
```

### 2. Server Agent (per server)

```bash
cd server-agent

# Virtual environment
python3 -m venv .venv-agent
source .venv-agent/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env: set AGENT_API_KEY (use: openssl rand -hex 32)
nano .env

# Start
python -m uvicorn agent:app --host 0.0.0.0 --port 9100
```

Test the agent:
```bash
curl http://localhost:9100/health
curl -H "X-API-Key: jouw-key" http://localhost:9100/os
```

### 3. Central Dashboard

```bash
cd central-dashboard

# Virtual environment
python3 -m venv .venv-dashboard
source .venv-dashboard/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env: set DASHBOARD_API_KEY + agent URLs/keys
nano .env

# Start
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

### 4. Docker (optional)

```bash
docker compose up -d
```

## Configuration

### Server Agent (`.env`)

```ini
# Required: API key (min 16 chars)
AGENT_API_KEY=your-secure-key-here

# Optional (defaults shown)
AGENT_HOST=0.0.0.0
AGENT_PORT=9100
```

### Central Dashboard (`.env`)

```ini
# Required: Dashboard API key (min 16 chars)
DASHBOARD_API_KEY=your-secure-key-here

# Optional (defaults shown)
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8000

# Agent configuration
# Pattern: AGENT_<ID>_URL and AGENT_<ID>_KEY
AGENT_UMBRELOS_URL=http://192.168.1.217:9100
AGENT_UMBRELOS_KEY=agent-key-for-umbrelos

AGENT_UBUNTU_URL=http://192.168.1.3:9100
AGENT_UBUNTU_KEY=agent-key-for-ubuntu
```

> **Security**: `.env` files are in `.gitignore` and should never be committed.  
> Generate keys with: `openssl rand -hex 32`

## Deployment

### Standalone Agent (using systemd)

Create `/etc/systemd/system/homelab-agent.service`:

```ini
[Unit]
Description=Homelab Dashboard Server Agent
After=network.target

[Service]
Type=simple
User=homelab
WorkingDirectory=/opt/homelab-dashboard/server-agent
EnvironmentFile=/opt/homelab-dashboard/server-agent/.env
ExecStart=/opt/homelab-dashboard/server-agent/.venv-agent/bin/uvicorn agent:app --host 0.0.0.0 --port 9100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now homelab-agent
```

### Docker Agent

```bash
docker run -d \
  --name homelab-agent \
  --restart unless-stopped \
  -p 9100:9100 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /proc:/host/proc:ro \
  -v /:/host:ro \
  --env-file ./server-agent/.env \
  homelab-agent
```

### Dashboard (Docker)

```bash
docker run -d \
  --name homelab-dashboard \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file ./central-dashboard/.env \
  homelab-dashboard
```

## Security

- **API keys**: Required for all POST actions (container start/stop/restart)
- **Timing attacks**: `secrets.compare_digest()` used for key comparison
- **Rate limiting**: Per-IP rolling window (100 requests / 60 seconds)
- **CORS**: Restricted to known dashboard origins
- **Audit logging**: All requests logged with IP, method, path, status, duration
- **No hardcoded secrets**: All keys via environment variables (`.env`)
- **Non-root container**: Agents run as unprivileged user

## Design System

### Colors

| Color | Hex | Usage |
|-------|-----|-------|
| White | `#FFFFFF` | Background |
| Black | `#000000` | Text, accents, active states |
| Gray | `#E5E7EB` | Borders, dividers, skeletons |

### Typography

| Element | Font | Size |
|---------|------|------|
| H1 | Playfair Display 900 | `clamp(2.5rem, 5vw, 4.5rem)` |
| H2 | Playfair Display 700 | `clamp(1.75rem, 3.5vw, 3rem)` |
| H3 | Playfair Display 700 | `clamp(1.25rem, 2.5vw, 2rem)` |
| Body | Helvetica Neue | `1rem` (16px) |
| Meta | Helvetica Neue | `0.8125rem` (13px) |

### Principles

- Zero gradients, shadows, or blur effects
- Sharp corners (`border-radius: 0`)
- High contrast (pure black on white)
- Heavy padding (64px+ between sections)
- Touch-optimized: 48×48px minimum targets, 56px buttons

## Project Structure

```
homelab-dashboard/
├── central-dashboard/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── models/              # Pydantic data models
│   │   ├── routers/             # API endpoints
│   │   ├── services/            # Agent HTTP client
│   │   └── static/              # Frontend
│   │       ├── css/style.css
│   │       ├── js/app.js
│   │       └── index.html
│   ├── Dockerfile
│   ├── .env.example
│   └── requirements.txt
├── server-agent/
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── os_info.py
│   │   ├── system.py
│   │   └── docker.py
│   ├── agent.py                 # FastAPI app
│   ├── Dockerfile
│   ├── .env.example
│   └── requirements.txt
├── .gitignore
├── docker-compose.yml
└── README.md
```

## Development

```bash
# Start both services locally
# Terminal 1: Server agent
cd server-agent
source .venv-agent/bin/activate
python -m uvicorn agent:app --host 127.0.0.1 --port 9100 --reload

# Terminal 2: Dashboard
cd central-dashboard
source .venv-dashboard/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open http://127.0.0.1:8000.

## License

MIT
