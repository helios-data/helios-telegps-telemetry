"""
Packet decoding pipeline: AX.25 frame → TNC2 string → APRS parse.
"""

import sys

import aprslib

from decoder.formatting import hexdump

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

    parsed = _parse_aprs(tnc2, debug)
    if parsed is not None:
        return parsed

    # aprslib rejected the payload, but the AX.25 frame itself was well-formed —
    # e.g. a tracker transmitting 0xff filler in the compressed lat/lon fields
    # while it has no GPS fix.  Pass the addresses and raw info field through so
    # the packet is still visible downstream instead of vanishing.
    return _unparsed_packet(tnc2)


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


def _unparsed_packet(tnc2: str) -> dict | None:
    """
    Build a minimal packet dict from a TNC2 string aprslib could not parse.

    Mirrors the shape aprslib returns (`from`/`to`/`path`/`raw`) minus any
    position fields, so every downstream consumer keeps working unchanged.
    """
    src, sep, rest = tnc2.partition(">")
    if not sep:
        return None

    addrs, _, _ = rest.partition(":")
    parts = addrs.split(",")

    return {
        "from":   src,
        "to":     parts[0],
        "path":   parts[1:],
        "format": "unparsed",
        "raw":    _printable(tnc2),
    }


def _printable(text: str) -> str:
    """
    Escape non-printable characters as <0xNN>, matching Direwolf's own display.

    The info field arrives as latin-1, so it can hold bytes that are illegal in
    a protobuf `string`, unwritable in the CSV's encoding, or invisible on the
    console.  Escaping keeps the payload lossless and greppable everywhere.
    """
    return "".join(c if 32 <= ord(c) < 127 else f"<0x{ord(c):02x}>" for c in text)


def _parse_aprs(tnc2: str, debug: bool) -> dict | None:
    try:
        return dict(aprslib.parse(tnc2))
    except aprslib.ParseError as exc:
        if debug:
            print(f"[DEBUG] APRS parse error: {exc} — {tnc2!r}", file=sys.stderr)
        return None
    except aprslib.UnknownFormat as exc:
        if debug:
            print(f"[DEBUG] Unknown APRS format: {exc} — {tnc2!r}", file=sys.stderr)
        return None
    except Exception as exc:
        print(
            f"[ERROR] Unexpected APRS parse error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None
