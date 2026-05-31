"""
CSV logger for APRS packet data.
"""

import csv
from datetime import datetime
from pathlib import Path


COLUMNS = [
    "recv_time",
    "from_call",
    "to_call",
    "path",
    "packet_format",
    "latitude",
    "longitude",
    "altitude_m",   # meters (aprslib converts from feet)
    "speed_kmh",    # km/h  (aprslib converts from knots)
    "course_deg",
    "symbol_table",
    "symbol",
    "comment",
    "raw",
]


def packet_to_row(packet: dict) -> list:
    """Convert a parsed APRS packet dict to a CSV row aligned with COLUMNS."""
    return [
        datetime.now().isoformat(timespec='milliseconds'),
        packet.get('from', ''),
        packet.get('to', ''),
        packet.get('path', ''),
        packet.get('format', ''),
        packet.get('latitude', ''),
        packet.get('longitude', ''),
        packet.get('altitude', ''),
        packet.get('speed', ''),
        packet.get('course', ''),
        packet.get('symbol_table', ''),
        packet.get('symbol', ''),
        packet.get('comment', ''),
        packet.get('raw', ''),
    ]


class CsvLogger:
    """
    Writes APRS packet rows to a CSV file.

    Opens the file on __enter__ and writes the header row immediately,
    so a zero-packet run still produces a valid (header-only) CSV.

    Args:
        path: Destination file path. Parent directories are created if needed.

    Usage:
        with CsvLogger("/data/aprs.csv") as log:
            log.write(packet)
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._file = None
        self._writer = None

    def __enter__(self) -> "CsvLogger":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(COLUMNS)
        return self

    def __exit__(self, *_) -> None:
        if self._file:
            self._file.close()

    def write(self, packet: dict) -> None:
        """Append one packet as a CSV row and flush immediately."""
        assert self._writer is not None, "CsvLogger must be used as a context manager"
        self._writer.writerow(packet_to_row(packet))
        if self._file:
            self._file.flush()
