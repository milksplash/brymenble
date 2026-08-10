"""Show the SDK's ASSUMED connection state so it can be checked against the
physical BM78xBT meter.

This drives the same logic the bridge uses (``wait_frame`` + ``is_connected``)
and prints what the SDK *believes* is happening, so you can compare it with
what the meter is actually doing (turn it off, switch functions, HOLD, etc.):

    [HH:MM:SS] STREAMING             link=up  last=0.2s  ACV 0.0066 V
    [HH:MM:SS] PAUSED (link up)      link=up  silent=8.3s  last=ACV 0.0066 V
                                     (assumed function-switch/HOLD; reconnect
                                     only after the pause cap)
    [HH:MM:SS] LINK DOWN             is_connected=False — reconnecting...

States:

* ``STREAMING``          — BLE link up AND frames are arriving.
* ``PAUSED (link up)``   — link still up but no frame for a while. The bridge
                          treats this as a function-switch/HOLD pause and does
                          NOT reconnect (bounded by the pause cap).
* ``LINK DOWN``          — ``is_connected`` False: the bridge treats this as a
                          power-off and reconnects.
* ``RECONNECTING``       — a reconnect is in progress.

NOTE: only ONE BLE connection is allowed — stop the bridge (or any other app
connected to the meter) before running this.

Run with ``-v`` to log every reading and the SDK's notify-gap DEBUG lines.

Usage:
    .venv\\Scripts\\python.exe tools\\connection_state.py [MAC] [--password 0000]
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime

# Allow running directly as `python tools\\connection_state.py` from anywhere.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
))

from brymen import BrymenClient, DEFAULT_PASSWORD, find_meters, format_reading  # noqa: E402

STREAMING = "STREAMING"
PAUSED = "PAUSED (link up)"
LINK_DOWN = "LINK DOWN"
RECONNECTING = "RECONNECTING"
NO_FRAME = "connected, no frame yet"


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _reading_str(reading) -> str:
    """Short display of the last reading, for comparison with the meter LCD."""
    if reading is None:
        return "?"
    if reading.is_overload:
        return f"{reading.function_name} OL"
    if reading.is_ascii:
        return f"{reading.function_name} {reading.ascii_text or '?'}"
    return f"{reading.function_name} {format_reading(reading)}"


def _retry_log(attempt: int, max_retries, error: Exception) -> None:
    label = f"retry {attempt}" if max_retries is None else f"retry {attempt}/{max_retries}"
    print(f"[{_ts()}] {label}: {error}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "mac", nargs="?", help="meter MAC (XX:XX:...); if omitted, the first "
        "meter found by scanning is used"
    )
    p.add_argument("--password", default=DEFAULT_PASSWORD,
                   help="4-digit connection password (default: 0000)")
    p.add_argument("--interval", type=float, default=2.0,
                   help="how often link/data state is checked (default: 2.0s)")
    p.add_argument("--pause-cap", type=float, default=60.0,
                   help="link-up silence before a reconnect is forced "
                        "(default: 60.0s)")
    p.add_argument("--heartbeat", type=float, default=5.0,
                   help="reprint the current state this often even if it "
                        "hasn't changed (default: 5.0s; 0 disables)")
    p.add_argument("--sync-rtc", action="store_true",
                   help="sync the meter's RTC to the host clock on connect")
    p.add_argument("--verbose", "-v", action="count", default=0,
                   help="log every reading and SDK DEBUG (notify gaps)")
    return p


async def _run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    mac = args.mac
    if mac is None:
        print("Scanning for a BM78xBT meter... (retrying until one is found)",
              file=sys.stderr)
        while True:
            meters = await find_meters()
            if meters:
                mac = meters[0].address
                print(f"Using {meters[0].name or 'BM78xBT'} at {mac}")
                break
            print("No BM78xBT meters in range yet — retrying in 5s...",
                  file=sys.stderr)
            await asyncio.sleep(5.0)

    client = BrymenClient(mac, args.password, sync_rtc_on_connect=args.sync_rtc)

    last_state: str | None = None
    last_print = 0.0
    silence_since: float | None = None
    last_frame_at: float | None = None
    last_reading = None

    def report(state: str, detail: str) -> None:
        nonlocal last_state, last_print
        now = time.monotonic()
        if args.verbose or state != last_state or (
            args.heartbeat and now - last_print >= args.heartbeat
        ):
            print(f"[{_ts()}] {state:<20} {detail}", flush=True)
            last_print = now
        last_state = state

    try:
        await client.ensure_connected(retries=None, on_retry=_retry_log)
        print(f"[{_ts()}] connected to {mac} — is_connected={client.is_connected}")
        report(NO_FRAME, "waiting for first frame...")

        while True:
            frame = await client.wait_frame(timeout=args.interval)

            if frame is not None:
                now = time.monotonic()
                gap = None if last_frame_at is None else now - last_frame_at
                last_frame_at = now
                silence_since = None
                last_reading = frame.readings[0] if frame.readings else None
                gap_txt = f"{gap:0.1f}" if gap is not None else "?"
                report(STREAMING, f"link=up last={gap_txt}s {_reading_str(last_reading)}")
                continue

            # No frame for one interval. Decide pause vs power-off (bridge logic).
            if client.is_connected:
                now = time.monotonic()
                if silence_since is None:
                    silence_since = now
                silent = now - silence_since
                report(
                    PAUSED,
                    f"link=up silent={silent:0.1f}s last={_reading_str(last_reading)} "
                    f"(assumed function-switch/HOLD; reconnect only after "
                    f"{args.pause_cap:g}s)",
                )
                if silent >= args.pause_cap:
                    report(RECONNECTING, f"pause cap ({args.pause_cap:g}s) reached — forcing reconnect")
                    silence_since = None
                    await client.ensure_connected(retries=None, on_retry=_retry_log)
                continue

            # is_connected is False: assumed power-off / out of range.
            report(LINK_DOWN, "is_connected=False — reconnecting")
            silence_since = None
            await client.ensure_connected(retries=None, on_retry=_retry_log)
    finally:
        await client.close()
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
