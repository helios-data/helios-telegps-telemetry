#!/bin/bash
set -e

AUDIO_DEVICE="${AUDIO_DEVICE:-hw:0,0}"
MYCALL="${MYCALL:-N0CALL}"
KISS_PORT="${KISS_PORT:-8001}"

# Generate a temporary Direwolf config
DWCONF=$(mktemp /tmp/direwolf.XXXXXX.conf)
sed \
    -e "s|AUDIO_DEVICE_PLACEHOLDER|${AUDIO_DEVICE}|g" \
    -e "s|MYCALL_PLACEHOLDER|${MYCALL}|g" \
    "$(dirname "$0")/direwolf.conf" \
    > "$DWCONF"

cleanup() {
    echo ""
    echo "[run.sh] Shutting down..."
    kill "$DIREWOLF_PID" 2>/dev/null || true
    rm -f "$DWCONF"
}
trap cleanup EXIT INT TERM

echo "[run.sh] Starting Direwolf (device=${AUDIO_DEVICE}, callsign=${MYCALL})..."
direwolf -c "$DWCONF" &
DIREWOLF_PID=$!

echo "[run.sh] Waiting for KISS port ${KISS_PORT}..."
for i in $(seq 1 30); do
    if python3 -c "import socket; socket.create_connection(('localhost', ${KISS_PORT}), timeout=1).close()" 2>/dev/null; then
        echo "[run.sh] KISS port ready."
        break
    fi
    sleep 0.5
done

uv run python src/main.py "$@"
