#!/bin/bash
set -e

# Parse direwolf-specific flags first; everything else is forwarded to main.py.
# Flags here take precedence over environment variables of the same name.
#
#   --aprs-baud  1200|9600   Direwolf modem baud rate (default: 1200)
#   --audio-device <dev>     ALSA capture device (default: auto)
#   --mycall <call>          Station callsign (default: N0CALL)

APRS_BAUD="${APRS_BAUD:-1200}"
MYCALL="${MYCALL:-N0CALL}"
KISS_PORT="${KISS_PORT:-8001}"
AUDIO_DEVICE="${AUDIO_DEVICE:-auto}"

remaining=()
while [[ $# -gt 0 ]]; do
    case $1 in
        --aprs-baud)    APRS_BAUD="$2";    shift 2 ;;
        --audio-device) AUDIO_DEVICE="$2"; shift 2 ;;
        --mycall)       MYCALL="$2";       shift 2 ;;
        *)              remaining+=("$1"); shift   ;;
    esac
done

if [ "$AUDIO_DEVICE" = "auto" ]; then
    capture=$(ls /dev/snd/pcmC*D*c 2>/dev/null | head -1)
    if [ -n "$capture" ]; then
        base="${capture##*/}"   # pcmC1D0c
        base="${base#pcmC}"     # 1D0c
        card="${base%%D*}"      # 1
        dev="${base#*D}"; dev="${dev%c}"  # 0
        AUDIO_DEVICE="plughw:${card},${dev}"
        echo "[INIT] Auto-detected audio capture device: ${AUDIO_DEVICE} (${capture})"
    else
        AUDIO_DEVICE="hw:1,0"
        echo "[WARN] No ALSA capture device found, falling back to hw:1,0"
    fi
fi

sed \
    -e "s|AUDIO_DEVICE_PLACEHOLDER|${AUDIO_DEVICE}|g" \
    -e "s|MYCALL_PLACEHOLDER|${MYCALL}|g" \
    -e "s|MODEM_BAUD_PLACEHOLDER|${APRS_BAUD}|g" \
    /etc/direwolf/direwolf.conf.template \
    > /tmp/direwolf.conf

echo "[INIT] Starting Direwolf (device=${AUDIO_DEVICE}, callsign=${MYCALL}, baud=${APRS_BAUD})..."
direwolf -c /tmp/direwolf.conf &

echo "[INIT] Waiting for KISS port ${KISS_PORT}..."
for i in $(seq 1 30); do
    if python3 -c "import socket; socket.create_connection(('localhost', ${KISS_PORT}), timeout=1).close()" 2>/dev/null; then
        echo "[INIT] KISS port ready."
        break
    fi
    sleep 0.5
done

exec python src/main.py "${remaining[@]}"
