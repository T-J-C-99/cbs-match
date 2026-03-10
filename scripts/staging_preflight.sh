#!/bin/bash
set -euo pipefail

echo "=== Stage 2 Staging Preflight ==="

required=(API_BASE_URL ADMIN_TOKEN)
missing=0
for key in "${required[@]}"; do
  if [ -z "${!key:-}" ]; then
    echo "[ERROR] Missing env var: $key"
    missing=1
  else
    echo "[OK] $key set"
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Set required env vars before proceeding."
  exit 1
fi

echo "[INFO] Checking health endpoint..."
curl -fsS "$API_BASE_URL/health" >/dev/null
echo "[OK] Health endpoint reachable"

echo "[INFO] Running staging smoke..."
python scripts/smoke_staging.py
