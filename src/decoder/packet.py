"""
Packet decoding pipeline: AX.25 frame → TNC2 string → APRS parse.
"""

import re
import sys

import aprslib

from decoder.formatting import hexdump

_ALT_FT_RE = re.compile(r'/A=(\d+)')

_MIN_AX25_LEN = 17  # 2 addrs (14) + ctrl (1) + pid (1) + 1 info byte


def decode_packet(raw_ax25: bytes, debug: bool = False) -> dict | None:
    """
    Decode a raw AX.25 frame from KISS into a parsed APRS packet dict.

    Args:
        raw_ax25: Raw AX.25 bytes (KISS framing already stripped).
        debug:    If True, emit diagnostic output to stderr.

    Returns:
        Parsed APRS fields as a dict, or None if decoding fails at any stage.
    """
    if len(raw_ax25) < _MIN_AX25_LEN:
        if debug:
            print(
                f"[DEBUG] Frame too short ({len(raw_ax25)} bytes), skipping",
                file=sys.stderr,
            )
        return None

    if debug:
        print(f"[DEBUG] Raw AX.25 ({len(raw_ax25)} bytes):", file=sys.stderr)
        print(hexdump(raw_ax25), file=sys.stderr)

    tnc2 = _ax25_to_tnc2(raw_ax25)
    if tnc2 is None:
        return None

    if debug:
        print(f"[DEBUG] TNC2: {tnc2}", file=sys.stderr)

    return _parse_aprs(tnc2, debug)


def _ax25_to_tnc2(frame: bytes) -> str | None:
    """
    Convert raw AX.25 frame bytes to a TNC2-format string for aprslib.

    AX.25 address order: DEST, SRC, DIGI...
    TNC2 format:         SRC>DEST,DIGI1,DIGI2:INFO
    """
    pos = 0
    addrs = []

    while pos + 7 <= len(frame):
        raw = frame[pos:pos + 7]
        callsign = ''.join(chr(raw[i] >> 1) for i in range(6)).rstrip()
        ssid_byte = raw[6]
        ssid = (ssid_byte >> 1) & 0x0F
        # H bit (bit 7): has-been-repeated flag on digipeater addresses
        h_bit = bool(ssid_byte & 0x80)

        addr = f"{callsign}-{ssid}" if ssid else callsign
        if h_bit and len(addrs) >= 2:
            addr = f"{addr}*"

        addrs.append(addr)
        pos += 7

        if ssid_byte & 0x01:  # address extension bit: 1 = last address
            break
    else:
        print("[WARNING] AX.25 address field did not terminate", file=sys.stderr)
        return None

    if len(addrs) < 2:
        print("[WARNING] AX.25 frame has fewer than 2 address fields", file=sys.stderr)
        return None

    if pos + 2 > len(frame):
        print("[WARNING] AX.25 frame truncated before control/PID bytes", file=sys.stderr)
        return None

    ctrl = frame[pos]
    pid  = frame[pos + 1]
    pos += 2

    if ctrl != 0x03 or pid != 0xF0:
        return None  # Not an APRS UI frame; silently discard

    info = frame[pos:]

    try:
        info_str = info.decode('latin-1')
    except Exception:
        return None

    # TNC2: SRC>DEST,DIGI1,DIGI2,...:INFO
    src        = addrs[1]
    dest       = addrs[0]
    path_parts = [dest] + addrs[2:]
    path       = ','.join(path_parts)

    return f"{src}>{path}:{info_str}"


def _parse_aprs(tnc2: str, debug: bool) -> dict | None:
    try:
        return dict(aprslib.parse(tnc2))
    except (aprslib.ParseError, aprslib.UnknownFormat) as exc:
        if debug:
            label = "APRS parse error" if isinstance(exc, aprslib.ParseError) else "Unknown APRS format"
            print(f"[DEBUG] {label}: {exc} — {tnc2!r}", file=sys.stderr)
        return _fallback_parse(tnc2, debug)
    except Exception as exc:
        print(
            f"[ERROR] Unexpected APRS parse error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


def _fallback_parse(tnc2: str, debug: bool) -> dict | None:
    """Extract callsign and altitude from a packet aprslib cannot fully decode (e.g. no GPS lock)."""
    try:
        header, _, info = tnc2.partition(':')
        src, _, path_str = header.partition('>')
        path_parts = path_str.split(',') if path_str else []
        dest = path_parts[0] if path_parts else ''
        digipeaters = path_parts[1:] if len(path_parts) > 1 else []

        result: dict = {
            'from': src.strip(),
            'to': dest,
            'path': digipeaters,
            'format': 'partial',
            'raw': tnc2,
        }

        alt_match = _ALT_FT_RE.search(info)
        if alt_match:
            result['altitude'] = int(alt_match.group(1)) * 0.3048  # feet → meters

        if debug:
            alt_str = f", alt={result['altitude']:.0f}m" if 'altitude' in result else ""
            print(f"[DEBUG] Fallback parse: from={result['from']}{alt_str} (no position fix)", file=sys.stderr)

        return result
    except Exception:
        return None
