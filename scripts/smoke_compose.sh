#!/bin/bash
# Smoke test for CBS Match - boots docker compose and verifies services
# Usage: ./scripts/smoke_compose.sh [cleanup]

set -e

TIMEOUT=120
API_URL="http://localhost:8000"
WEB_URL="http://localhost:3000"

echo "=== CBS Match Smoke Test ==="

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    docker compose down
    echo "Done."
}

# If called with 'cleanup' arg, just clean up and exit
if [ "$1" == "cleanup" ]; then
    cleanup
    exit 0
fi

# Check for questions.json (required by docker-compose)
if [ ! -f "questions.json" ]; then
    echo "WARNING: questions.json not found - creating placeholder"
    echo '{"questions":[]}' > questions.json
fi

# Start services
echo "Starting services with docker compose..."
docker compose up -d --build

# Trap to ensure cleanup on exit
trap 'echo "Test interrupted"; docker compose logs --tail=50; cleanup' INT TERM

# Wait for API
echo "Waiting for API at $API_URL/health (timeout: ${TIMEOUT}s)..."
start_time=$(date +%s)
api_ready=false

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -ge $TIMEOUT ]; then
        echo "ERROR: Timeout waiting for API"
        break
    fi
    
    if curl -sf "$API_URL/health" > /dev/null 2>&1; then
        echo "✓ API is ready (${elapsed}s)"
        api_ready=true
        break
    fi
    
    sleep 2
done

# Wait for Web
echo "Waiting for Web at $WEB_URL (timeout: ${TIMEOUT}s)..."
start_time=$(date +%s)
web_ready=false

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -ge $TIMEOUT ]; then
        echo "ERROR: Timeout waiting for Web"
        break
    fi
    
    if curl -sf "$WEB_URL" > /dev/null 2>&1; then
        echo "✓ Web is ready (${elapsed}s)"
        web_ready=true
        break
    fi
    
    sleep 2
done

# Results
echo ""
echo "=== Results ==="

if [ "$api_ready" = true ] && [ "$web_ready" = true ]; then
    echo "✓ All services are healthy"
    echo ""
    echo "Services are running. To stop them, run:"
    echo "  ./scripts/smoke_compose.sh cleanup"
    echo "Or manually:"
    echo "  docker compose down"
    exit 0
else
    echo "✗ Some services failed to start"
    echo ""
    echo "=== Logs (last 100 lines) ==="
    docker compose logs --tail=100
    echo ""
    echo "To clean up, run: ./scripts/smoke_compose.sh cleanup"
    exit 1
fi