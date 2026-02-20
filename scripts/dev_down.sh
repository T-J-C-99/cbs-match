#!/bin/bash

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="$ROOT_DIR/.dev"

# Kill process on port 8000 if DEV_DOWN_KILL_8000 is set
if [ "$DEV_DOWN_KILL_8000" = "true" ]; then
    PORT_PID=$(lsof -i :8000 -t 2>/dev/null || echo "")
    if [ -n "$PORT_PID" ]; then
        echo "Killing process on port 8000 (PID: $PORT_PID)"
        kill -9 $PORT_PID 2>/dev/null || true
    fi
fi

# Kill API process
if [ -f "$DEV_DIR/api.pid" ]; then
    API_PID=$(cat "$DEV_DIR/api.pid")
    if kill -0 $API_PID 2>/dev/null; then
        echo "Stopping API (PID: $API_PID)"
        kill $API_PID 2>/dev/null || true
    fi
    rm -f "$DEV_DIR/api.pid"
fi

# Kill web process
if [ -f "$DEV_DIR/web.pid" ]; then
    WEB_PID=$(cat "$DEV_DIR/web.pid")
    if kill -0 $WEB_PID 2>/dev/null; then
        echo "Stopping web (PID: $WEB_PID)"
        kill $WEB_PID 2>/dev/null || true
    fi
    rm -f "$DEV_DIR/web.pid"
fi

echo "Development services stopped"