FROM python:3.11-slim

WORKDIR /app

# Docker CLI nodig om met de Docker socket te praten
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agent code
COPY . .

EXPOSE 9100

# Start agent
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "9100"]
