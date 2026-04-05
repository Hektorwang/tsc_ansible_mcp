#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/venv"
PYTHON_BIN="$VENV_DIR/bin/python"
LOG_DIR="$SCRIPT_DIR/logs"

usage() {
    echo "Usage: $0 {start|stop|restart|status}"
    echo ""
    echo "Commands:"
    echo "  start   Start unified server (MCP + REST API on port 8500)"
    echo "  stop    Stop server"
    echo "  restart Restart server"
    echo "  status  Show server status"
    echo ""
    echo "Endpoints:"
    echo "  MCP Server:  http://localhost:8500/mcp"
    echo "  REST API:    http://localhost:8500/docs"
    exit 1
}

start_server() {
    echo "Starting unified server on port 8500..."
    nohup "$PYTHON_BIN" bin/server.py > "$LOG_DIR/server.log" 2>&1 &
    echo $! > "$LOG_DIR/server.pid"
    echo "Server started (PID: $(cat "$LOG_DIR/server.pid"))"
    echo ""
    echo "Endpoints:"
    echo "  MCP Server:  http://localhost:8500/mcp"
    echo "  REST API:    http://localhost:8500/docs"
}

stop_server() {
    if [ -f "$LOG_DIR/server.pid" ]; then
        PID=$(cat "$LOG_DIR/server.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "Server stopped (PID: $PID)"
        fi
        rm -f "$LOG_DIR/server.pid"
    fi
}

show_status() {
    echo "Server Status:"
    echo "=============="
    if [ -f "$LOG_DIR/server.pid" ]; then
        PID=$(cat "$LOG_DIR/server.pid")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Server: RUNNING (PID: $PID)"
            echo ""
            echo "Endpoints:"
            echo "  MCP Server:  http://localhost:8500/mcp"
            echo "  REST API:    http://localhost:8500/docs"
        else
            echo "Server: STOPPED (stale PID file)"
        fi
    else
        echo "Server: NOT RUNNING"
    fi
}

mkdir -p "$LOG_DIR" "$SCRIPT_DIR/var"

case "${1:-}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 2
        start_server
        ;;
    status)
        show_status
        ;;
    *)
        usage
        ;;
esac
