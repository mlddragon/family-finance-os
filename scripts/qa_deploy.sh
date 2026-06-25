#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

QA_URL="${QA_URL:-http://127.0.0.1:28081/api/status}"
QA_HEALTH_RETRIES="${QA_HEALTH_RETRIES:-30}"
QA_HEALTH_INTERVAL_SEC="${QA_HEALTH_INTERVAL_SEC:-2}"

echo "Stopping legacy dillon-qa compose project if present..."
docker compose -p dillon-qa down --remove-orphans 2>/dev/null || true

echo "Rebuilding QA Docker instance..."
make qa-up

echo "Waiting for QA health check at ${QA_URL}..."
for attempt in $(seq 1 "${QA_HEALTH_RETRIES}"); do
  if response="$(curl -sf "${QA_URL}" 2>/dev/null)"; then
    if printf '%s' "${response}" | grep -q '"app_env":"qa"'; then
      echo "QA instance healthy (attempt ${attempt}/${QA_HEALTH_RETRIES})."
      printf '%s\n' "${response}"
      exit 0
    fi
    echo "QA responded but app_env is not qa (attempt ${attempt}/${QA_HEALTH_RETRIES})."
  else
    echo "QA not ready yet (attempt ${attempt}/${QA_HEALTH_RETRIES})."
  fi
  sleep "${QA_HEALTH_INTERVAL_SEC}"
done

echo "QA health check failed after ${QA_HEALTH_RETRIES} attempts." >&2
exit 1
