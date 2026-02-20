# NotesOS — Bare-Metal VPS Deployment Guide

Everything runs directly on the machine. No Docker.

---

## Architecture

```
Internet
   │
   ▼
┌──────────────┐
│ Nginx (:443) │  SSL termination + reverse proxy
└──┬───────┬───┘
   │       │
   │       ├── /api/*  /ws/*  /docs  /health → uvicorn (:8000)
   │       └── /*                             → next start (:3000)
   │
   ├── PostgreSQL 16 + pgvector (:5432)
   ├── Redis 7 (:6379)
   └── 3 background workers (systemd)
```

**Processes (all managed by systemd):**

| Service | What it does |
|---------|-------------|
| `notesos-backend` | FastAPI API (uvicorn, 2 workers) |
| `notesos-frontend` | Next.js production server |
| `notesos-worker-chunking` | Resource chunking + embeddings |
| `notesos-worker-grading` | Voice/answer grading |
| `notesos-worker-factcheck` | Fact checking |

---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| OS | Ubuntu 22.04+ / Debian 12+ |
| RAM | 4 GB (8 GB recommended) |
| Disk | 30 GB |
| Domain | A record pointing to your VPS IP |
| Ports | 22, 80, 443 open |

The setup script installs everything else (Python 3.11, Node 20, PostgreSQL 16, Redis, Nginx, Certbot).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USER/NotesOS.git
cd NotesOS

# 2. Run setup (installs system deps, builds everything, starts services)
chmod +x deploy.sh
sudo ./deploy.sh setup
# → You'll be prompted to edit .env with your secrets

# 3. Get SSL
sudo ./deploy.sh ssl
```

Done. Your app is at `https://YOUR_DOMAIN`.

---

## Step-by-Step

### 1. DNS

Point your domain to your VPS IP:

```
Type: A
Name: notesos (or @ for root domain)
Value: YOUR_VPS_IP
```

### 2. SSH in and clone

```bash
ssh root@YOUR_VPS_IP
git clone https://github.com/YOUR_USER/NotesOS.git
cd NotesOS
```

### 3. Run setup

```bash
chmod +x deploy.sh
sudo ./deploy.sh setup
```

The script will:
1. Install system packages (Python 3.11, build tools, tesseract, poppler, libmagic)
2. Install Node.js 20
3. Install PostgreSQL 16 + pgvector extension
4. Install Redis
5. Create a `notesos` system user
6. Copy files to `/opt/notesos`
7. **Pause** so you can edit `/opt/notesos/.env` — fill in your values
8. Create the PostgreSQL database and user
9. Set up Python venv + install backend deps
10. Run Alembic migrations
11. Build the Next.js frontend
12. Configure Nginx (HTTP only for now)
13. Install + start all systemd services
14. Configure firewall (ports 22, 80, 443)

### 4. Edit your environment

When prompted, fill in `/opt/notesos/.env`:

```bash
nano /opt/notesos/.env
```

**Must change:**

| Variable | Example |
|----------|---------|
| `DOMAIN` | `notesos.example.com` |
| `POSTGRES_PASSWORD` | `openssl rand -hex 32` |
| `JWT_SECRET` | `openssl rand -hex 64` |
| `NEXT_PUBLIC_API_URL` | `https://notesos.example.com` |
| `CORS_ORIGINS` | `["https://notesos.example.com"]` |
| AI keys | Your API keys for Anthropic, OpenAI, Voyage, Serper, DeepSeek |
| Cloudinary | Your cloud name, API key/secret, upload preset |

### 5. Get SSL

```bash
sudo ./deploy.sh ssl
```

This runs Certbot, gets a Let's Encrypt certificate, and switches Nginx to HTTPS. Auto-renewal is handled by the `certbot` systemd timer.

### 6. Verify

```bash
./deploy.sh status

# Should show:
#   ● notesos-backend: active
#   ● notesos-frontend: active
#   ● notesos-worker-chunking: active
#   ● notesos-worker-grading: active
#   ● notesos-worker-factcheck: active
#   ● postgresql: active
#   ● redis-server: active
#   ● nginx: active
```

```bash
curl https://YOUR_DOMAIN/health
# → {"status":"healthy","database":"connected","redis":"connected"}
```

---

## Ongoing Operations

### Deploy an update

```bash
cd NotesOS
git pull
sudo ./deploy.sh deploy
```

This syncs files, updates deps, runs migrations, rebuilds frontend, and restarts all services.

### View logs

```bash
./deploy.sh logs                  # All notesos services
./deploy.sh logs backend          # Just the API
./deploy.sh logs frontend         # Just Next.js
./deploy.sh logs worker-chunking  # Just the chunking worker

# Or directly:
journalctl -u notesos-backend -f
```

### Restart / stop

```bash
sudo ./deploy.sh restart    # Restart all
sudo ./deploy.sh stop       # Stop all
```

### Run migrations only

```bash
sudo ./deploy.sh migrate
```

---

## File Layout on Server

```
/opt/notesos/                    ← App root
├── .env                         ← Production secrets (600 perms)
├── backend/
│   ├── venv/                    ← Python virtualenv
│   ├── app/                     ← FastAPI application
│   ├── alembic/                 ← DB migrations
│   └── requirements.txt
├── frontend/
│   ├── node_modules/
│   ├── .next/                   ← Built frontend
│   └── ...
├── deploy/
│   ├── notesos-backend.service
│   ├── notesos-frontend.service
│   ├── notesos-worker-chunking.service
│   ├── notesos-worker-grading.service
│   └── notesos-worker-factcheck.service
└── nginx/
    ├── nginx.conf
    └── conf.d/notesos.conf

/etc/systemd/system/             ← Service files (copied by setup)
/etc/nginx/conf.d/notesos.conf   ← Nginx vhost (copied by setup)
/etc/letsencrypt/                ← SSL certs (managed by certbot)
```

---

## Firewall

Setup configures `ufw` automatically. If you need manual control:

```bash
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP (redirect + ACME)
sudo ufw allow 443/tcp    # HTTPS
sudo ufw enable
```

PostgreSQL (5432) and Redis (6379) are **not** exposed — they listen on localhost only.

---

## Backups

### Database dump

```bash
sudo -u postgres pg_dump notesos > backup_$(date +%Y%m%d).sql
```

### Restore

```bash
sudo -u postgres psql notesos < backup.sql
```

### Automate daily backups

```bash
# Add to root's crontab:
sudo crontab -e

# Daily at 3 AM, keep 14 days:
0 3 * * * pg_dump -U postgres notesos | gzip > /opt/backups/notesos_$(date +\%Y\%m\%d).sql.gz && find /opt/backups -name "notesos_*.sql.gz" -mtime +14 -delete
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Service won't start | `journalctl -u notesos-backend -n 50` — check logs |
| 502 Bad Gateway | Backend not up yet; `./deploy.sh status`, wait, retry |
| SSL cert error | `sudo ./deploy.sh ssl` — check DNS resolves first |
| DB connection refused | `systemctl status postgresql` |
| Workers not processing | `./deploy.sh logs worker-chunking` — likely missing API keys |
| CORS errors | Check `CORS_ORIGINS` in `.env` matches your frontend URL exactly |
| Permission denied | Files must be owned by `notesos` user: `chown -R notesos:notesos /opt/notesos` |
| Port already in use | `ss -tlnp | grep :8000` — kill the conflicting process |

---

## Resource Sizing

| Load | vCPU | RAM | Notes |
|------|------|-----|-------|
| 1–10 users | 2 | 4 GB | Minimum viable |
| 10–50 users | 4 | 8 GB | Recommended |
| 50+ users | 8+ | 16 GB | Consider separating DB to its own server |
