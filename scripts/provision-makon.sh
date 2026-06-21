#!/usr/bin/env bash
# ============================================================
# MAKON bare-metal provisioning for a fresh Ubuntu 22.04/24.04 server.
# Mirrors the working sova-mebel setup (systemd, not Docker).
#
# Run as root on the NEW server (212.193.24.193):
#   bash provision-makon.sh
#
# Optional inputs placed in /root beforehand:
#   /root/bk.sql.gz    -> gzipped pg_dump from sova (restored if DB empty)
#   /root/barber.env   -> sova's backend/.env (copied + patched for prod)
#
# Idempotent: safe to re-run. Does NOT run certbot (do that after the
# check-host reachability gate — see the printed instructions at the end).
# ============================================================
set -euo pipefail

# ---- Config (edit if needed) ----
DOMAIN="app.makon.men"
APP_DIR="/opt/Barber-kombat"
REPO="https://github.com/ExecuteTyT/Barber-kombat.git"
DB_NAME="barber_kombat"
DB_USER="barber"
DB_PASS="barber123"          # localhost-only; matches sova
DUMP="/root/bk.sql.gz"        # restored only if DB has no tables
ENVSRC="/root/barber.env"     # copied to backend/.env if present
NODE_MAJOR="20"

say() { echo -e "\n\033[1;33m== $1 ==\033[0m"; }

# ---- 1. System packages ----
say "1/10 System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  git curl ca-certificates gnupg \
  postgresql postgresql-contrib \
  redis-server \
  nginx \
  python3 python3-venv python3-dev build-essential libpq-dev \
  certbot python3-certbot-nginx
systemctl enable --now postgresql redis-server nginx

# ---- 2. Node.js (NodeSource) ----
say "2/10 Node.js ${NODE_MAJOR}"
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -c2- | cut -d. -f1)" -lt 18 ]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi
node -v; npm -v

# ---- 3. Code ----
say "3/10 Repository"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin && git -C "$APP_DIR" checkout main && git -C "$APP_DIR" pull --ff-only
elif [ -n "${GITHUB_TOKEN:-}" ]; then
  # Private repo: clone with a one-time token, then strip it from stored config.
  git clone "https://${GITHUB_TOKEN}@github.com/ExecuteTyT/Barber-kombat.git" "$APP_DIR"
  git -C "$APP_DIR" remote set-url origin "$REPO"
  git -C "$APP_DIR" checkout main
else
  git clone "$REPO" "$APP_DIR"
  git -C "$APP_DIR" checkout main
fi

# ---- 4. Python venv + deps ----
say "4/10 Python venv"
cd "$APP_DIR/backend"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install --upgrade pip wheel
venv/bin/pip install -r requirements.txt

# ---- 5. Frontend build ----
say "5/10 Frontend build"
cd "$APP_DIR/frontend"
npm ci
npm run build            # relative /api -> same-origin, no VITE_API_URL needed

# ---- 6. PostgreSQL role + database ----
say "6/10 PostgreSQL role + database"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';"
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
  || sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"

# ---- 6b. Restore dump only if DB is empty ----
TBL=$(sudo -u postgres psql -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" "${DB_NAME}")
if [ "${TBL}" -eq 0 ] && [ -f "${DUMP}" ]; then
  say "6b. Restoring dump from ${DUMP}"
  gunzip -c "${DUMP}" | sudo -u postgres psql "${DB_NAME}"
  sudo -u postgres psql "${DB_NAME}" -c "REASSIGN OWNED BY postgres TO ${DB_USER};" 2>/dev/null || true
  sudo -u postgres psql -c "GRANT ALL ON DATABASE ${DB_NAME} TO ${DB_USER};"
  sudo -u postgres psql "${DB_NAME}" -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO ${DB_USER}; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO ${DB_USER};"
else
  echo "DB already has ${TBL} tables or no dump present — skipping restore."
fi

# ---- 7. .env ----
say "7/10 backend/.env"
ENVFILE="$APP_DIR/backend/.env"
if [ -f "${ENVSRC}" ] && [ ! -f "${ENVFILE}" ]; then
  cp "${ENVSRC}" "${ENVFILE}"
fi
if [ -f "${ENVFILE}" ]; then
  # Patch the prod-specific values, keep all secrets/tokens from sova as-is.
  sed -i \
    -e "s|^APP_ENV=.*|APP_ENV=production|" \
    -e "s|^APP_DEBUG=.*|APP_DEBUG=false|" \
    -e "s|^TELEGRAM_MINI_APP_URL=.*|TELEGRAM_MINI_APP_URL=https://${DOMAIN}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}|" \
    "${ENVFILE}"
  echo ".env patched (APP_ENV=production, MINI_APP_URL=https://${DOMAIN})."
else
  echo "!! No ${ENVFILE} and no ${ENVSRC}. Copy sova's backend/.env to ${ENVSRC} and re-run."
fi
chmod 600 "${ENVFILE}" 2>/dev/null || true

# ---- 8. Alembic migrations (noop if dump already at head) ----
say "8/10 Alembic migrations"
cd "$APP_DIR/backend"
venv/bin/alembic upgrade head || echo "!! alembic failed — check DATABASE_URL / .env"

# ---- 9. systemd units ----
say "9/10 systemd services"
BK="$APP_DIR/backend"
PY="$BK/venv/bin"

cat >/etc/systemd/system/barber-backend.service <<EOF
[Unit]
Description=MAKON Backend (uvicorn)
After=network.target postgresql.service redis-server.service
[Service]
WorkingDirectory=${BK}
EnvironmentFile=${BK}/.env
ExecStart=${PY}/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/barber-celery.service <<EOF
[Unit]
Description=MAKON Celery Worker
After=network.target redis-server.service postgresql.service
[Service]
WorkingDirectory=${BK}
EnvironmentFile=${BK}/.env
ExecStart=${PY}/celery -A app.tasks.celery_app worker --loglevel=info
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/barber-celery-beat.service <<EOF
[Unit]
Description=MAKON Celery Beat
After=network.target redis-server.service postgresql.service
[Service]
WorkingDirectory=${BK}
EnvironmentFile=${BK}/.env
ExecStart=${PY}/celery -A app.tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now barber-backend barber-celery barber-celery-beat
systemctl restart barber-backend barber-celery barber-celery-beat

# ---- 10. nginx (HTTP only; certbot adds 443 later) ----
say "10/10 nginx site (HTTP)"
cat >/etc/nginx/sites-available/makon <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    root ${APP_DIR}/frontend/dist;
    index index.html;
    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    location = /index.html {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
ln -sf /etc/nginx/sites-available/makon /etc/nginx/sites-enabled/makon
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# ---- Done ----
say "PROVISION DONE"
echo "Backend health (local):"
curl -s http://127.0.0.1:8000/api/health || true
echo
echo "Next steps:"
echo "  1) Verify global reachability on port 80:"
echo "       https://check-host.net/check-http?host=http://${DOMAIN}/api/health"
echo "     All (or nearly all) nodes must be green BEFORE issuing the cert."
echo "  2) Issue TLS cert (adds 443 + redirect automatically):"
echo "       certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m islamsabirzyanov@gmail.com --redirect"
echo "  3) Re-check: curl -sI https://${DOMAIN}/api/health"
echo
echo "Service status:"
systemctl --no-pager --type=service | grep barber || true
