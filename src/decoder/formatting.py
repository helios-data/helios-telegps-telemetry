"""
Display helpers: hex dumps and formatted APRS packet printing.
"""


def hexdump(data: bytes, prefix: str = "  ") -> str:
    """Format bytes as a hex dump with ASCII representation."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_part  = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:04x}: {hex_part:<48} |{ascii_part}|")
    return "\n".join(lines)


def print_compact(index: int, packet: dict) -> None:
    """Print a single-line summary of an APRS packet."""
    src     = packet.get('from', '?')
    lat     = packet.get('latitude')
    lon     = packet.get('longitude')
    alt     = packet.get('altitude')
    speed   = packet.get('speed')
    comment = packet.get('comment', '')
    fmt     = packet.get('format', '')

    pos_str = f"{lat:.5f},{lon:.5f}" if lat is not None and lon is not None else "no-pos"
    parts   = [pos_str]
    if alt   is not None: parts.append(f"alt={alt:.1f}m")
    if speed is not None: parts.append(f"spd={speed:.1f}km/h")
    if comment:           parts.append(comment[:40])

    print(f"[{index}] {src:<9} [{fmt:12}] {' | '.join(parts)}")


def print_verbose(index: int, packet: dict) -> None:
    """Print all fields of an APRS packet."""
    print(f"[{index}] APRS Packet:")
    for key, val in packet.items():
        if key != 'raw':
            print(f"    {key:<16} {val}")
    if 'raw' in packet:
        print(f"    {'raw':<16} {packet['raw']}")
    print()
