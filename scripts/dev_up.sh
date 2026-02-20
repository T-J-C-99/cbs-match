#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="$ROOT_DIR/.dev"
API_BASE_URL="http://127.0.0.1:8000"
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"

# Create .dev directory if it doesn't exist
mkdir -p "$DEV_DIR"

# Check if API is already healthy
check_api_health() {
    curl -s -o /dev/null -w "%{http_code}" "$API_BASE_URL/survey/active" 2>/dev/null || echo "000"
}

# Check if port 8000 is in use
check_port_8000() {
    lsof -i :8000 -t 2>/dev/null || echo ""
}

# Kill process on port 8000 if DEV_UP_KILL_EXISTING_API is set
if [ "$DEV_UP_KILL_EXISTING_API" = "true" ]; then
    PORT_PID=$(check_port_8000)
    if [ -n "$PORT_PID" ]; then
        echo "Killing existing process on port 8000 (PID: $PORT_PID)"
        kill -9 $PORT_PID 2>/dev/null || true
        sleep 1
    fi
fi

# Check if API is already running and healthy
HEALTH_CODE=$(check_api_health)
if [ "$HEALTH_CODE" = "200" ]; then
    echo "API already running and healthy at $API_BASE_URL"
    echo "Reusing existing API process"
else
    # Check if port 8000 is occupied
    PORT_PID=$(check_port_8000)
    if [ -n "$PORT_PID" ]; then
        echo "ERROR: Port 8000 is occupied but API is not healthy (health check returned $HEALTH_CODE)"
        echo "Set DEV_UP_KILL_EXISTING_API=true to kill the existing process"
        exit 1
    fi
    
    echo "Starting API on $API_BASE_URL"
    ( cd "$ROOT_DIR/api"; source .venv/bin/activate; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 ) > "$DEV_DIR/api.log" 2>&1 &
    API_PID=$!
    echo $API_PID > "$DEV_DIR/api.pid"
    
    echo "Waiting for API readiness at /survey/active"
    for i in {1..60}; do
        HEALTH_CODE=$(check_api_health)
        if [ "$HEALTH_CODE" = "200" ]; then
            echo "API is ready!"
            break
        fi
        if [ $i -eq 60 ]; then
            echo "ERROR: API failed to start within 60 seconds"
            echo "Check logs at $DEV_DIR/api.log"
            exit 1
        fi
        sleep 1
    done
fi

# Start web
echo "Starting web on http://localhost:3000"
( cd "$ROOT_DIR/web"; API_BASE_URL="$API_BASE_URL" NEXT_PUBLIC_API_BASE_URL="$NEXT_PUBLIC_API_BASE_URL" npm run dev ) > "$DEV_DIR/web.log" 2>&1 &
WEB_PID=$!
echo $WEB_PID > "$DEV_DIR/web.pid"

# Wait for web to be ready
echo "Waiting for web to start..."
for i in {1..30}; do
    if curl -s -o /dev/null http://localhost:3000 2>/dev/null; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Warning: Web may not be fully started yet"
    fi
    sleep 1
done

# Get LAN IP for physical device testing
LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "N/A")

echo ""
echo "Development services started"
echo "Web URL: http://localhost:3000"
echo "API URL: $API_BASE_URL"
echo "iOS simulator API base URL: http://localhost:8000"
echo "Android emulator API base URL: http://10.0.2.2:8000"
if [ "$LAN_IP" != "N/A" ]; then
    echo "Physical device API base URL: http://$LAN_IP:8000"
    echo "Set this in the mobile Settings screen API base URL override for physical device testing."
fi
echo "Logs: $DEV_DIR/api.log and $DEV_DIR/web.log"
echo "Stop background services with: npm run dev:down"
echo ""

# Start mobile in foreground
echo "Starting Expo in foreground. Press i for iOS, a for Android, or scan QR for device."
cd "$ROOT_DIR"
npm run mobile