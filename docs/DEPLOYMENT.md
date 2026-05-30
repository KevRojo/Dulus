# Dulus Deployment Guide

> Deploy Dulus anywhere — from your laptop to the cloud.

---

## Table of Contents

- [Local Development](#local-development)
- [Docker / Docker Compose](#docker--docker-compose)
- [Cloud Deployment](#cloud-deployment)
- [Self-Hosted Server](#self-hosted-server)
- [Telegram Bot](#telegram-bot)
- [Systemd Service](#systemd-service)

---

## Local Development

### Prerequisites

- Python 3.11+
- pip or pipx
- (Optional) PortAudio for voice
- (Optional) tkinter for GUI

### Install from Source

```bash
git clone https://github.com/KevRojo/Dulus && cd Dulus
pip install -e ".[full]"   # editable install with all extras
```

### Run the REPL

```bash
dulus                        # interactive REPL
dulus -p "hello world"       # one-shot piped input
dulus --model gpt-4o         # specify model
```

### Run the WebChat

```bash
dulus-webchat --port 5050 --open
```

Or from the REPL:
```
/webchat
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=...
export NVIDIA_API_KEY=nvapi-...
```

---

## Docker / Docker Compose

### Quick Start

```bash
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/docker-compose.yml
curl -fsSLO https://raw.githubusercontent.com/KevRojo/Dulus/main/.env.example
mv .env.example .env
# Edit .env with your API keys
docker compose up -d
```

Services:
- **Dulus REPL** — Available via `docker compose exec dulus dulus`
- **WebChat** — Available at `http://localhost:5050`
- **Persistent memory** — Stored in `dulus-memory` Docker volume

### Docker Compose Configuration

```yaml
version: '3.8'
services:
  dulus:
    image: ghcr.io/kevrojo/dulus:latest
    ports:
      - "5050:5050"
    volumes:
      - dulus-memory:/root/.dulus
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    restart: unless-stopped

volumes:
  dulus-memory:
```

### Build from Dockerfile

```bash
docker build -t dulus:local .
docker run -it -p 5050:5050 -v dulus-memory:/root/.dulus dulus:local
```

### Multi-Platform Images

Available for: `linux/amd64`, `linux/arm64`

```bash
docker pull ghcr.io/kevrojo/dulus:latest
```

---

## Cloud Deployment

### AWS (EC2)

```bash
# Launch an EC2 instance (t3.medium or larger recommended)
# SSH in and run:
sudo apt update && sudo apt install -y docker.io docker-compose
git clone https://github.com/KevRojo/Dulus && cd Dulus
cp .env.example .env
# Edit .env with your keys
sudo docker compose up -d
```

Configure security group to allow port 5050 (WebChat) and 22 (SSH).

### Google Cloud Platform (Compute Engine)

```bash
# Create instance
gcloud compute instances create dulus-server \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=dulus-web

# SSH and setup
gcloud compute ssh dulus-server
# Follow Docker setup above
```

### Azure (Container Instances)

```bash
az container create \
  --resource-group myResourceGroup \
  --name dulus \
  --image ghcr.io/kevrojo/dulus:latest \
  --ports 5050 \
  --environment-variables ANTHROPIC_API_KEY=sk-ant-...
```

### Railway / Render / Fly.io

For PaaS deployment, use the Dockerfile:

```dockerfile
FROM ghcr.io/kevrojo/dulus:latest
ENV PORT=8080
CMD ["dulus-webchat", "--port", "8080", "--host", "0.0.0.0"]
```

---

## Self-Hosted Server

### Production WebChat

For production use, the full `webchat_server.py` provides:
- Multi-session support (each user gets isolated state)
- Authentication hooks
- WebSocket-like SSE streaming
- Persistent sessions across restarts

```bash
dulus-webchat-server --port 5050 --host 0.0.0.0
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name dulus.yourdomain.com;

    location / {
        proxy_pass http://localhost:5050;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d dulus.yourdomain.com
```

---

## Telegram Bot

### Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) on Telegram
2. Get your bot token
3. Get your chat ID (message [@userinfobot](https://t.me/userinfobot))

### From the REPL

```
/telegram YOUR_BOT_TOKEN YOUR_CHAT_ID
```

### Multi-User Mode

```
/telegram YOUR_BOT_TOKEN CHAT_ID_1,CHAT_ID_2,CHAT_ID_3
```

Each authorized chat gets its own context. Dulus tracks who sent each message.

### Persistent Bot

Add to your config (`~/.dulus/config.json`):

```json
{
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_ids": "CHAT_ID_1,CHAT_ID_2"
}
```

---

## Systemd Service

For running Dulus as a system service on Linux:

### Create Service File

```bash
sudo tee /etc/systemd/system/dulus.service << 'EOF'
[Unit]
Description=Dulus AI Agent
After=network.target

[Service]
Type=simple
User=dulus
WorkingDirectory=/home/dulus
ExecStart=/usr/local/bin/dulus-webchat-server --port 5050 --host 0.0.0.0
Restart=always
RestartSec=10
Environment="ANTHROPIC_API_KEY=sk-ant-..."
Environment="OPENAI_API_KEY=sk-..."

[Install]
WantedBy=multi-user.target
EOF
```

### Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable dulus
sudo systemctl start dulus
sudo systemctl status dulus
```

### Logs

```bash
sudo journalctl -u dulus -f
```

---

> *Named after the bird, not the rocket. We keep flying.*
