#!/bin/bash
set -e

if [ -z "$AUDIO_DEVICE" ] || [ "$AUDIO_DEVICE" = "auto" ]; then
    capture=$(ls /dev/snd/pcmC*D*c 2>/dev/null | head -1)
    if [ -n "$capture" ]; then
        base="${capture##*/}"   # pcmC1D0c
        base="${base#pcmC}"     # 1D0c
        card="${base%%D*}"      # 1
        dev="${base#*D}"; dev="${dev%c}"  # 0
        AUDIO_DEVICE="hw:${card},${dev}"
        echo "[INIT] Auto-detected audio capture device: ${AUDIO_DEVICE} (${capture})"
    else
        AUDIO_DEVICE="hw:0,0"
        echo "[WARN] No ALSA capture device found, falling back to hw:0,0"
    fi
fi

MYCALL="${MYCALL:-N0CALL}"
KISS_PORT="${KISS_PORT:-8001}"

sed \
    -e "s|AUDIO_DEVICE_PLACEHOLDER|${AUDIO_DEVICE}|g" \
    -e "s|MYCALL_PLACEHOLDER|${MYCALL}|g" \
    /etc/direwolf/direwolf.conf.template \
    > /tmp/direwolf.conf

echo "[INIT] Starting Direwolf (device=${AUDIO_DEVICE}, callsign=${MYCALL})..."
direwolf -c /tmp/direwolf.conf &

echo "[INIT] Waiting for KISS port ${KISS_PORT}..."
for i in $(seq 1 30); do
    if python3 -c "import socket; socket.create_connection(('localhost', ${KISS_PORT}), timeout=1).close()" 2>/dev/null; then
        echo "[INIT] KISS port ready."
        break
    fi
    sleep 0.5
done

exec python src/main.py "$@"
