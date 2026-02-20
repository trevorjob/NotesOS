#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════
# NotesOS — Bare-Metal VPS Deployment Script
# ═══════════════════════════════════════════════════════════
#
# Usage:
#   First time:    sudo ./deploy.sh setup
#   Get SSL:       sudo ./deploy.sh ssl
#   Update/deploy: sudo ./deploy.sh deploy
#   DB migrate:    sudo ./deploy.sh migrate
#   Status:        ./deploy.sh status
#   Logs:          ./deploy.sh logs [service]
#   Restart:       sudo ./deploy.sh restart
#   Stop:          sudo ./deploy.sh stop

APP_DIR="/opt/notesos"
APP_USER="notesos"
ENV_FILE="${APP_DIR}/.env"

SERVICES=(
    notesos-backend
    notesos-frontend
    notesos-worker-chunking
    notesos-worker-grading
    notesos-worker-factcheck
)

# ── Helpers ──────────────────────────────────────────────
info()  { echo -e "\033[1;34m→ $*\033[0m"; }
ok()    { echo -e "\033[1;32m✓ $*\033[0m"; }
err()   { echo -e "\033[1;31m✗ $*\033[0m" >&2; }
need_root() { [[ $EUID -eq 0 ]] || { err "Run with sudo"; exit 1; }; }

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        err "${ENV_FILE} not found. Run setup first or copy .env.production.example to ${ENV_FILE}"
        exit 1
    fi
}

# ── setup ────────────────────────────────────────────────
cmd_setup() {
    need_root
    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    info "=== NotesOS Bare-Metal Setup ==="
    echo ""

    # ── 1. System packages ───────────────────────────────
    info "Installing system packages..."
    apt-get update
    apt-get install -y \
        python3.11 python3.11-venv python3.11-dev \
        build-essential libpq-dev \
        tesseract-ocr poppler-utils libmagic1 \
        nginx certbot python3-certbot-nginx \
        curl git
    ok "System packages installed"

    # ── 2. Node.js 20 ───────────────────────────────────
    if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
        info "Installing Node.js 20..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
        ok "Node.js $(node -v) installed"
    else
        ok "Node.js $(node -v) already installed"
    fi

    # ── 3. PostgreSQL 16 + pgvector ─────────────────────
    if ! command -v psql &>/dev/null; then
        info "Installing PostgreSQL 16..."
        apt-get install -y postgresql-common
        /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
        apt-get install -y postgresql-16 postgresql-16-pgvector
        systemctl enable --now postgresql
        ok "PostgreSQL 16 installed"
    else
        ok "PostgreSQL already installed"
        # Still try to install pgvector
        apt-get install -y postgresql-16-pgvector 2>/dev/null || true
    fi

    # ── 4. Redis ────────────────────────────────────────
    if ! command -v redis-server &>/dev/null; then
        info "Installing Redis..."
        apt-get install -y redis-server
        systemctl enable --now redis-server
        ok "Redis installed"
    else
        ok "Redis already installed"
    fi

    # ── 5. Create app user ──────────────────────────────
    if ! id "$APP_USER" &>/dev/null; then
        info "Creating user ${APP_USER}..."
        useradd --system --create-home --shell /bin/bash "$APP_USER"
        ok "User ${APP_USER} created"
    fi

    # ── 6. Copy project files ───────────────────────────
    info "Copying project to ${APP_DIR}..."
    mkdir -p "$APP_DIR"
    rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='.next' --exclude='__pycache__' \
        "${SCRIPT_DIR}/" "${APP_DIR}/"
    chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"
    ok "Files copied"

    # ── 7. Environment file ─────────────────────────────
    if [ ! -f "$ENV_FILE" ]; then
        cp "${APP_DIR}/.env.production.example" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        chown "${APP_USER}:${APP_USER}" "$ENV_FILE"
        echo ""
        err "IMPORTANT: Edit ${ENV_FILE} with your production values!"
        echo "   nano ${ENV_FILE}"
        echo ""
        echo "   Required: DOMAIN, POSTGRES_PASSWORD, JWT_SECRET,"
        echo "   NEXT_PUBLIC_API_URL, CORS_ORIGINS, AI keys, Cloudinary keys"
        echo ""
        read -rp "Press Enter after editing .env to continue (or Ctrl+C to abort)..."
    fi

    source "$ENV_FILE"

    # ── 8. PostgreSQL database ──────────────────────────
    info "Setting up PostgreSQL database..."
    local DB_NAME="${POSTGRES_DB:-notesos}"
    local DB_USER="${POSTGRES_USER:-notesos}"
    local DB_PASS="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}"

    sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" \
        | grep -q 1 || sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"

    sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" \
        | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

    sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

    ok "Database ${DB_NAME} ready"

    # ── 9. Backend venv + deps ──────────────────────────
    info "Setting up backend Python environment..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/backend
        python3.11 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    "
    ok "Backend dependencies installed"

    # ── 10. Run migrations ──────────────────────────────
    info "Running database migrations..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/backend
        source venv/bin/activate
        set -a; source ${ENV_FILE}; set +a
        export DATABASE_URL='postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}'
        export DATABASE_SSL=false
        alembic upgrade head
    "
    ok "Migrations applied"

    # ── 11. Frontend build ──────────────────────────────
    info "Building frontend..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/frontend
        npm ci
        NEXT_PUBLIC_API_URL='${NEXT_PUBLIC_API_URL:?Set NEXT_PUBLIC_API_URL in .env}' npm run build
    "
    ok "Frontend built"

    # ── 12. Nginx config ────────────────────────────────
    info "Configuring Nginx..."
    cp "${APP_DIR}/nginx/nginx.conf" /etc/nginx/nginx.conf
    cp "${APP_DIR}/nginx/conf.d/notesos.conf" /etc/nginx/conf.d/notesos.conf
    rm -f /etc/nginx/sites-enabled/default

    local DOMAIN="${DOMAIN:?Set DOMAIN in .env}"
    sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" /etc/nginx/conf.d/notesos.conf

    # Comment out SSL lines until cert exists
    if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
        info "SSL cert not found yet — starting HTTP only (run './deploy.sh ssl' next)"
        # Create a temporary HTTP-only config
        cat > /etc/nginx/conf.d/notesos.conf << TMPCONF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
TMPCONF
    fi

    nginx -t
    systemctl enable --now nginx
    systemctl reload nginx
    ok "Nginx configured"

    # ── 13. Systemd services ────────────────────────────
    info "Installing systemd services..."

    # Write the DATABASE_URL into the env file if not already there
    grep -q "^DATABASE_URL=" "$ENV_FILE" && \
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}|" "$ENV_FILE" || \
        echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}" >> "$ENV_FILE"

    grep -q "^REDIS_URL=" "$ENV_FILE" || echo "REDIS_URL=redis://localhost:6379" >> "$ENV_FILE"
    grep -q "^DATABASE_SSL=" "$ENV_FILE" || echo "DATABASE_SSL=false" >> "$ENV_FILE"

    for svc in "${SERVICES[@]}"; do
        cp "${APP_DIR}/deploy/${svc}.service" "/etc/systemd/system/${svc}.service"
    done

    systemctl daemon-reload

    for svc in "${SERVICES[@]}"; do
        systemctl enable "$svc"
        systemctl start "$svc"
    done

    ok "All services started"

    # ── 14. Firewall ────────────────────────────────────
    if command -v ufw &>/dev/null; then
        info "Configuring firewall..."
        ufw allow 22/tcp   >/dev/null 2>&1 || true
        ufw allow 80/tcp   >/dev/null 2>&1 || true
        ufw allow 443/tcp  >/dev/null 2>&1 || true
        ufw --force enable >/dev/null 2>&1 || true
        ok "Firewall configured (22, 80, 443)"
    fi

    echo ""
    ok "=== Setup complete! ==="
    echo ""
    echo "  Your app is running at: http://${DOMAIN}"
    echo ""
    echo "  Next step: sudo ./deploy.sh ssl"
    echo ""
}

# ── ssl ──────────────────────────────────────────────────
cmd_ssl() {
    need_root
    check_env
    source "$ENV_FILE"
    local DOMAIN="${DOMAIN:?Set DOMAIN in .env}"

    info "Obtaining SSL certificate for ${DOMAIN}..."

    mkdir -p /var/www/certbot

    certbot certonly --webroot -w /var/www/certbot \
        -d "${DOMAIN}" \
        --email "admin@${DOMAIN}" \
        --agree-tos \
        --no-eff-email \
        --non-interactive

    ok "SSL certificate obtained"

    # Now install the full HTTPS nginx config
    info "Switching Nginx to HTTPS..."
    cp "${APP_DIR}/nginx/conf.d/notesos.conf" /etc/nginx/conf.d/notesos.conf
    sed -i "s/YOUR_DOMAIN/${DOMAIN}/g" /etc/nginx/conf.d/notesos.conf

    nginx -t
    systemctl reload nginx

    ok "Nginx now serving HTTPS"
    echo ""
    echo "  Your app is live at: https://${DOMAIN}"
    echo ""
    echo "  Auto-renewal is handled by the certbot systemd timer."
    echo "  Check with: systemctl list-timers | grep certbot"
    echo ""
}

# ── deploy (update) ─────────────────────────────────────
cmd_deploy() {
    need_root
    check_env
    source "$ENV_FILE"

    local SCRIPT_DIR
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

    info "Deploying update..."

    # Pull latest if it's a git repo
    if [ -d "${SCRIPT_DIR}/.git" ]; then
        info "Pulling latest code..."
        cd "$SCRIPT_DIR"
        sudo -u "$APP_USER" git pull || info "Git pull failed — using local files"
    fi

    # Sync files
    info "Syncing files to ${APP_DIR}..."
    rsync -a --exclude='.git' --exclude='node_modules' --exclude='venv' \
        --exclude='.next' --exclude='__pycache__' --exclude='.env' \
        "${SCRIPT_DIR}/" "${APP_DIR}/"
    chown -R "${APP_USER}:${APP_USER}" "$APP_DIR"

    # Backend deps
    info "Updating backend dependencies..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/backend
        source venv/bin/activate
        pip install -r requirements.txt -q
    "

    # Migrations
    info "Running migrations..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/backend
        source venv/bin/activate
        set -a; source ${ENV_FILE}; set +a
        alembic upgrade head
    "
    ok "Migrations applied"

    # Frontend rebuild
    info "Rebuilding frontend..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/frontend
        npm ci
        NEXT_PUBLIC_API_URL='${NEXT_PUBLIC_API_URL}' npm run build
    "
    ok "Frontend built"

    # Restart services
    info "Restarting services..."
    for svc in "${SERVICES[@]}"; do
        systemctl restart "$svc"
    done
    ok "All services restarted"

    echo ""
    ok "Deploy complete!"
}

# ── migrate ──────────────────────────────────────────────
cmd_migrate() {
    check_env
    info "Running database migrations..."
    sudo -u "$APP_USER" bash -c "
        cd ${APP_DIR}/backend
        source venv/bin/activate
        set -a; source ${ENV_FILE}; set +a
        alembic upgrade head
    "
    ok "Migrations applied"
}

# ── status ───────────────────────────────────────────────
cmd_status() {
    echo ""
    echo "NotesOS Services:"
    echo "─────────────────────────────────────────"
    for svc in "${SERVICES[@]}"; do
        local state
        state=$(systemctl is-active "$svc" 2>/dev/null || echo "not found")
        if [ "$state" = "active" ]; then
            echo -e "  \033[32m●\033[0m ${svc}: active"
        else
            echo -e "  \033[31m●\033[0m ${svc}: ${state}"
        fi
    done
    echo ""

    echo "Infrastructure:"
    echo "─────────────────────────────────────────"
    for svc in postgresql redis-server nginx; do
        local state
        state=$(systemctl is-active "$svc" 2>/dev/null || echo "not found")
        if [ "$state" = "active" ]; then
            echo -e "  \033[32m●\033[0m ${svc}: active"
        else
            echo -e "  \033[31m●\033[0m ${svc}: ${state}"
        fi
    done
    echo ""
}

# ── logs ─────────────────────────────────────────────────
cmd_logs() {
    local target="${1:-}"
    if [ -n "$target" ]; then
        journalctl -u "notesos-${target}" -f --no-hostname -n 100
    else
        journalctl -u "notesos-*" -f --no-hostname -n 100
    fi
}

# ── restart ──────────────────────────────────────────────
cmd_restart() {
    need_root
    info "Restarting all NotesOS services..."
    for svc in "${SERVICES[@]}"; do
        systemctl restart "$svc"
    done
    systemctl reload nginx
    ok "All services restarted"
}

# ── stop ─────────────────────────────────────────────────
cmd_stop() {
    need_root
    info "Stopping all NotesOS services..."
    for svc in "${SERVICES[@]}"; do
        systemctl stop "$svc"
    done
    ok "All services stopped"
}

# ── main ─────────────────────────────────────────────────
case "${1:-help}" in
    setup)   cmd_setup ;;
    ssl)     cmd_ssl ;;
    deploy)  cmd_deploy ;;
    migrate) cmd_migrate ;;
    logs)    cmd_logs "${2:-}" ;;
    status)  cmd_status ;;
    restart) cmd_restart ;;
    stop)    cmd_stop ;;
    *)
        echo "NotesOS Bare-Metal Deployment"
        echo ""
        echo "Usage: sudo ./deploy.sh <command>"
        echo ""
        echo "Commands:"
        echo "  setup    First-time setup (installs everything, builds, starts)"
        echo "  ssl      Obtain SSL certificate via Let's Encrypt"
        echo "  deploy   Pull latest, rebuild, migrate, restart"
        echo "  migrate  Run Alembic migrations only"
        echo "  logs     Tail logs (optional: logs backend, logs frontend, logs worker-chunking)"
        echo "  status   Show all service statuses"
        echo "  restart  Restart all NotesOS services"
        echo "  stop     Stop all NotesOS services"
        ;;
esac
