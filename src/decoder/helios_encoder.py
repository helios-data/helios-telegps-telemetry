"""
Encode parsed APRS packets into helios.transport.AprsPacket protobuf bytes.

aprslib reports altitude in metres and speed in km/h; the wire format uses
feet and knots, so both are converted here.
"""

from helios.generated.helios.transport import AprsPacket, AprsPosition

_M_PER_FT     = 0.3048
_KMH_PER_KNOT = 1.852


def encode_packet(packet: dict) -> bytes:
    """
    Serialise a parsed APRS packet dict into AprsPacket protobuf bytes.

    Args:
        packet: Parsed APRS fields as returned by decode_packet().

    Returns:
        The serialised AprsPacket, ready to use as Helios event data.
    """
    fields = {
        "source":      str(packet.get("from", "")),
        "destination": str(packet.get("to", "")),
        "path":        [str(p) for p in (packet.get("path") or [])],
    }

    lat = packet.get("latitude")
    lon = packet.get("longitude")

    # payload oneof: a parsed position if we have coordinates, raw text otherwise
    if lat is not None and lon is not None:
        fields["position"] = _position(packet, float(lat), float(lon))
    else:
        fields["raw_info"] = _info_field(str(packet.get("raw", "")))

    return AprsPacket(**fields).SerializeToString()


def _info_field(raw: str) -> str:
    """Strip the TNC2 header, leaving the information field (the part after ':')."""
    _, sep, info = raw.partition(":")
    return info if sep else raw


def _position(packet: dict, lat: float, lon: float) -> AprsPosition:
    """Build an AprsPosition from the position fields of a parsed packet."""
    alt_m   = packet.get("altitude")
    speed   = packet.get("speed")
    course  = packet.get("course")
    comment = packet.get("comment")

    return AprsPosition(
        latitude=lat,
        longitude=lon,
        altitude_ft=float(alt_m) / _M_PER_FT if alt_m is not None else None,
        course_deg=float(course) if course is not None else None,
        speed_knots=float(speed) / _KMH_PER_KNOT if speed is not None else None,
        symbol=f"{packet.get('symbol_table', '')}{packet.get('symbol', '')}",
        comment=str(comment) if comment else None,
    )
