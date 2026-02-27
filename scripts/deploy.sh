#!/usr/bin/env bash
# ============================================================
# Deploy script for Barber Kombat
#
# Usage:
#   ./scripts/deploy.sh              # Full deploy
#   ./scripts/deploy.sh --migrate    # Run migrations only
#   ./scripts/deploy.sh --rollback   # Rollback last migration
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---- Pre-flight checks ----

check_env() {
    if [ ! -f .env ]; then
        log_error ".env file not found. Copy .env.production to .env and configure."
        exit 1
    fi
    log_info ".env file found"
}

check_ssl() {
    if [ ! -f ssl/fullchain.pem ] || [ ! -f ssl/privkey.pem ]; then
        log_warn "SSL certificates not found in ssl/"
        log_warn "Generate with: certbot certonly --standalone -d your-domain.com"
        log_warn "Then copy to ssl/fullchain.pem and ssl/privkey.pem"
    else
        log_info "SSL certificates found"
    fi
}

# ---- Commands ----

run_migrations() {
    log_info "Running database migrations..."
    docker compose exec -T backend alembic upgrade head
    log_info "Migrations complete"
}

rollback_migration() {
    log_info "Rolling back last migration..."
    docker compose exec -T backend alembic downgrade -1
    log_info "Rollback complete"
}

full_deploy() {
    check_env
    check_ssl

    log_info "Creating backup directory..."
    mkdir -p backups ssl

    log_info "Pulling latest images..."
    docker compose pull db redis

    log_info "Building application images..."
    docker compose build --parallel

    log_info "Starting infrastructure (db, redis)..."
    docker compose up -d db redis
    sleep 5

    log_info "Running migrations..."
    docker compose run --rm backend alembic upgrade head

    log_info "Starting all services..."
    docker compose up -d

    log_info "Waiting for health check..."
    sleep 10

    # Health check
    if docker compose exec -T nginx wget --spider -q http://localhost/api/health 2>/dev/null; then
        log_info "Health check passed!"
    else
        log_warn "Health check did not pass yet — services may still be starting."
    fi

    log_info "Deployment complete!"
    echo ""
    log_info "Services status:"
    docker compose ps
}

# ---- Main ----

show_status() {
    log_info "Services status:"
    docker compose ps
    echo ""
    log_info "Health summary:"
    docker compose ps --format "table {{.Name}}\t{{.Status}}" | grep -E "(healthy|unhealthy|starting)" || echo "  No health info available"
}

show_logs() {
    local SERVICE="${2:-}"
    if [ -n "$SERVICE" ]; then
        docker compose logs --tail=100 -f "$SERVICE"
    else
        docker compose logs --tail=50 -f
    fi
}

case "${1:-}" in
    --migrate)
        run_migrations
        ;;
    --rollback)
        rollback_migration
        ;;
    --status)
        show_status
        ;;
    --logs)
        show_logs "$@"
        ;;
    --help)
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  (no args)     Full deploy (build, migrate, start)"
        echo "  --migrate     Run database migrations only"
        echo "  --rollback    Rollback last migration"
        echo "  --status      Show services status"
        echo "  --logs [svc]  Tail logs (optionally for specific service)"
        echo "  --help        Show this help"
        ;;
    *)
        full_deploy
        ;;
esac
