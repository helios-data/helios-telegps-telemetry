"""
Async KISS TCP reader for Direwolf.

Connects to a KISS-over-TCP interface (Direwolf default: localhost:8001),
parses KISS framing, and yields raw AX.25 frames as bytes.
"""

import asyncio
import contextlib
import sys

_FEND = 0xC0   # frame delimiter
_FESC = 0xDB   # escape character
_TFEND = 0xDC  # escaped FEND value
_TFESC = 0xDD  # escaped FESC value
_MAX_FRAME = 4096
_RECONNECT_DELAY = 2.0


class KissReader:
    """
    Async KISS TCP reader.

    Args:
        host: Hostname or IP of the KISS TNC.
        port: TCP port of the KISS interface.
    """

    def __init__(self, host: str = "localhost", port: int = 8001) -> None:
        self._host = host
        self._port = port

    async def packets(self):
        """Yield raw AX.25 frames indefinitely, reconnecting on failure."""
        while True:
            try:
                reader, writer = await asyncio.open_connection(self._host, self._port)
                print(
                    f"[INFO] Connected to KISS TNC at {self._host}:{self._port}",
                    file=sys.stderr,
                )
                try:
                    async for frame in self._read_frames(reader):
                        yield frame
                except (ConnectionResetError, asyncio.IncompleteReadError, EOFError) as exc:
                    print(f"[WARNING] KISS connection lost: {exc}", file=sys.stderr)
                finally:
                    writer.close()
                    with contextlib.suppress(Exception):
                        await writer.wait_closed()
            except (ConnectionRefusedError, OSError) as exc:
                print(
                    f"[WARNING] Cannot connect to KISS TNC at {self._host}:{self._port}: {exc}. "
                    f"Retrying in {_RECONNECT_DELAY:.0f}s…",
                    file=sys.stderr,
                )
                await asyncio.sleep(_RECONNECT_DELAY)

    async def _read_frames(self, reader: asyncio.StreamReader):
        """Parse KISS frames from the TCP stream, yielding one AX.25 frame per KISS data frame."""
        buffer = bytearray()
        in_frame = False
        escaped = False
        cmd = None

        while True:
            data = await reader.read(4096)
            if not data:
                raise EOFError("KISS TCP connection closed by remote")

            for byte in data:
                if byte == _FEND:
                    # FEND ends the current frame (cmd==0x00 is a data frame)
                    if in_frame and buffer and cmd == 0x00:
                        yield bytes(buffer)
                    buffer.clear()
                    in_frame = False
                    escaped = False
                    cmd = None
                    continue

                if not in_frame:
                    # First byte after FEND is the KISS type byte
                    cmd = byte & 0x0F
                    in_frame = True
                    continue

                if byte == _FESC:
                    escaped = True
                    continue

                if escaped:
                    if byte == _TFEND:
                        byte = _FEND
                    elif byte == _TFESC:
                        byte = _FESC
                    escaped = False

                if len(buffer) < _MAX_FRAME:
                    buffer.append(byte)
