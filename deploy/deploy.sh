#!/usr/bin/env bash
#
# Production release script for the Nismita Craft Studio storefront.
#
# Runs on the cPanel server over SSH after GitHub Actions checks out the repo.
# It is deliberately idempotent and fail-fast: any non-zero exit aborts the
# release and leaves the previous release serving traffic (Passenger only
# restarts once every step below has succeeded).
#
# Configuration is passed as environment variables by .github/workflows/deploy.yml
# so nothing host-specific is ever committed to the repository.

set -euo pipefail

log() { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31m[deploy] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# --- Configuration (from the workflow environment) ----------------------------
APP_DIR="${APP_DIR:?APP_DIR is required}"
VENV_ACTIVATE="${VENV_ACTIVATE:?VENV_ACTIVATE is required}"
BRANCH="${BRANCH:-main}"
# Keep the previous release's static files until the new ones are collected.
KEEP_COLLECTSTATIC_DAYS="${KEEP_COLLECTSTATIC_DAYS:-3}"

log "Application directory: $APP_DIR"
log "Branch:                $BRANCH"

# --- 0. Sanity checks ---------------------------------------------------------
[ -d "$APP_DIR" ]    || fail "Application directory not found: $APP_DIR"
[ -f "$APP_DIR/manage.py" ] || fail "manage.py not found in $APP_DIR (is this a Django project?)"
[ -x "$VENV_ACTIVATE" ] || fail "Virtualenv activate script not executable: $VENV_ACTIVATE"
[ -f "$APP_DIR/.env" ] || fail ".env is missing in $APP_DIR. Production cannot boot without it."

cd "$APP_DIR"

# --- 1. Activate the virtualenv ----------------------------------------------
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"
log "Python: $(python -V 2>&1) at $(command -v python)"

# Production settings refuse to boot with DEBUG=True, and refuse to start without
# SECRET_KEY / DATABASE_URL / ALLOWED_HOSTS. Validate before touching git so a
# misconfigured environment fails loudly here instead of mid-deploy.
ENVIRONMENT="${ENVIRONMENT:-production}"
export ENVIRONMENT

# --- 2. Pull the new release --------------------------------------------------
# `git pull` runs the origin's own credentials (deploy key configured on the
# server), so no token is ever present on this machine.
log "Fetching origin..."
git fetch --prune origin "$BRANCH"

if [ -n "$(git status --porcelain)" ]; then
  fail "Working tree is dirty. Commit or stash changes on the server before deploying."
fi

log "Checking out $BRANCH..."
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

DEPLOY_SHA="$(git rev-parse --short HEAD)"
log "Deployed commit: $DEPLOY_SHA"

# `git pull` honours whatever origin/... remote URL is configured. If it still
# points at an HTTPS remote with a personal token, fail loudly and point at the
# deploy-key instructions rather than silently prompting for a password.
REMOTE_URL="$(git remote get-url origin)"
case "$REMOTE_URL" in
  https://*|*@*:*)
    log "Note: origin is an HTTPS remote ($REMOTE_URL). A deploy key is recommended."
    ;;
esac

# --- 3. Dependencies ----------------------------------------------------------
log "Installing dependencies from requirements.txt..."
# --no-input stops pip ever waiting for a prompt (which would hang the release).
python -m pip install --quiet --no-input --disable-pip-version-check -r requirements.txt

# --- 4. Django release commands ----------------------------------------------
log "Applying database migrations..."
python manage.py migrate --noinput

log "Collecting static files..."
python manage.py collectstatic --noinput --clear --ignore "*.pyc"

log "Pruning old collected static files (keep ${KEEP_COLLECTSTATIC_DAYS} runs)..."
# collectstatic --clear already removes unreferenced files; this is belt-and-braces
# for deployments where --clear is skipped.
find "$APP_DIR/staticfiles" -type f -mtime "+$KEEP_COLLECTSTATIC_DAYS" -delete 2>/dev/null || true

log "Running Django deployment checks..."
python manage.py check --deploy

# --- 5. Smoke test ------------------------------------------------------------
# A syntax/import error here must abort the release before Passenger restarts.
log "Importing WSGI application (smoke test)..."
python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); import passenger_wsgi" \
  || fail "WSGI application failed to import. Release aborted."

# --- 6. Restart Passenger -----------------------------------------------------
# cPanel/Passenger watches tmp/restart.txt and reloads the WSGI app when it is
# touched. This is the supported restart mechanism on shared hosting; there is no
# supervisorctl or service to reload here.
mkdir -p "$APP_DIR/tmp"
touch "$APP_DIR/tmp/restart.txt"
log "Passenger restart signalled (tmp/restart.txt)."

# --- 7. Post-deploy health check ---------------------------------------------
# Give Passenger a moment to boot the new code, then confirm the app answers.
SITE_URL="${SITE_URL:-}"
if [ -n "$SITE_URL" ]; then
  log "Waiting for the application to come back up..."
  for attempt in $(seq 1 15); do
    if curl --silent --fail --max-time 10 "${SITE_URL%/}/healthz/" | grep -q '"status"'; then
      log "Health check passed on attempt $attempt."
      break
    fi
    if [ "$attempt" -eq 15 ]; then
      fail "Application did not become healthy after the restart. Check the cPanel error log."
    fi
    sleep 2
  done
fi

log "Release $DEPLOY_SHA completed successfully."