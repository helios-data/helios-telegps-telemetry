"""
Entry point for the APRS telemetry decoder.

Receives APRS packets via KISS TCP from Direwolf (software TNC),
decodes AX.25 frames into APRS fields, and publishes to Helios.

Environment variables:
  KISS_HOST          Direwolf KISS TCP host        (default: localhost)
  KISS_PORT          Direwolf KISS TCP port        (default: 8001)
  HELIOS_NODE_URI    Helios node URI               (default: Helios.APRS.Receiver)
  CSV_OUTPUT_PATH    CSV log file path             (default: no logging)
"""

import argparse
import asyncio
import contextlib
import os
import sys

from helios import HeliosClient

from decoder.csv_logger import CsvLogger
from decoder.formatting import print_compact, print_verbose
from decoder.kiss_reader import KissReader
from decoder.packet import decode_packet


def build_config() -> argparse.Namespace:
    """Parse CLI args, falling back to environment variables for each option."""
    parser = argparse.ArgumentParser(
        description="Decode APRS packets from a Direwolf KISS TCP interface",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--kiss-host",
        default=os.environ.get("KISS_HOST", "localhost"),
        help="Direwolf KISS TCP host.  Env: KISS_HOST",
    )
    parser.add_argument(
        "--kiss-port",
        type=int,
        default=int(os.environ.get("KISS_PORT", 8001)),
        help="Direwolf KISS TCP port.  Env: KISS_PORT",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print all fields (default: compact one-liner)",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Hex-dump AX.25 bytes and TNC2 string to stderr",
    )
    parser.add_argument(
        "-o", "--output",
        default=os.environ.get("CSV_OUTPUT_PATH"),
        metavar="FILE",
        help="CSV log file path.  Env: CSV_OUTPUT_PATH",
    )
    return parser.parse_args()


async def _wait_first(*events: asyncio.Event) -> None:
    """Return as soon as any one of the given events is set."""
    tasks = [asyncio.create_task(e.wait()) for e in events]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await t


async def helios_manager(
    sdk: HeliosClient,
    ready: asyncio.Event,
    connection_lost: asyncio.Event,
    stop: asyncio.Event,
    retry_delays: tuple[int, ...] = (2, 5),
) -> None:
    """
    Manages the Helios connection lifecycle independently of the reader.

    Flow:
      1. Try to connect.
      2. On success  → set `ready`, then wait for `connection_lost` or `stop`.
      3. On failure  → clear `ready`, back off, then loop.
      4. On stop     → disconnect and return.
    """
    attempt = 0

    while not stop.is_set():
        connection_lost.clear()
        try:
            await sdk.connect()
            ready.set()
            label = "Connected" if attempt == 0 else "Reconnected"
            print(f"[Helios] {label}")
            attempt = 0

            await _wait_first(connection_lost, stop)
            ready.clear()

            if stop.is_set():
                break

            print("[Helios] Connection lost — scheduling reconnect…", file=sys.stderr)

        except Exception as exc:
            ready.clear()
            delay = retry_delays[min(attempt, len(retry_delays) - 1)]
            label = "Initial connection" if attempt == 0 else "Reconnect"
            print(
                f"[Helios] {label} failed: {exc}. Retrying in {delay}s…",
                file=sys.stderr,
            )
            attempt += 1
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=delay)

    ready.clear()
    with contextlib.suppress(Exception):
        await sdk.disconnect()
    print("[Helios] Manager exited.")


async def main_loop(args: argparse.Namespace) -> None:
    """Main loop — read AX.25 frames, decode to APRS, log and display."""
    print(f"Connecting to Direwolf KISS at {args.kiss_host}:{args.kiss_port}…")

    node_uri = os.environ.get("HELIOS_NODE_URI", "Helios.Services.TeleGPS")
    helios_sdk = HeliosClient(
        core_address="Helios",
        core_port=5000,
        node_uri=node_uri,
    )

    helios_ready    = asyncio.Event()
    connection_lost = asyncio.Event()
    stop            = asyncio.Event()

    manager_task = asyncio.create_task(
        helios_manager(helios_sdk, helios_ready, connection_lost, stop)
    )

    logger_ctx = CsvLogger(args.output) if args.output else _NullLogger()
    reader     = KissReader(args.kiss_host, args.kiss_port)

    try:
        with logger_ctx as logger:
            if args.output:
                print(f"Logging to {args.output}")
            print("Listening for APRS packets…\n")

            packet_count = 0

            async for raw in reader.packets():
                if len(raw) < 17:  # minimum valid AX.25 UI frame
                    continue

                packet_count += 1

                if args.debug:
                    print(f"[{packet_count}] Raw AX.25 ({len(raw)} bytes): {raw.hex()}")

                packet = decode_packet(raw, debug=args.debug)
                if packet is None:
                    continue

                if helios_ready.is_set():
                    try:
                        await helios_sdk.publish_event(
                            event_name="aprs",
                            data=bytes(raw),
                        )
                    except Exception as exc:
                        print(f"[Helios] Send failed: {exc}", file=sys.stderr)
                        helios_ready.clear()
                        connection_lost.set()

                if logger:
                    logger.write(packet)

                if args.verbose:
                    print_verbose(packet_count, packet)
                else:
                    print_compact(packet_count, packet)

    except KeyboardInterrupt:
        print("\nExiting…")
        if args.output:
            print(f"CSV saved to {args.output}")
    except Exception as exc:
        print(f"\n[ERROR] Unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
    finally:
        stop.set()
        await manager_task


class _NullLogger:
    def __enter__(self): return None
    def __exit__(self, *_): pass


if __name__ == "__main__":
    args = build_config()
    try:
        asyncio.run(main_loop(args))
    except KeyboardInterrupt:
        pass
