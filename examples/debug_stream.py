"""Debug/test script for the brymenble SDK — raw protocol stream dump.

Connects to a Brymen BM78xBT multimeter over BLE and prints every frame as it
arrives via ``display.py``: the full raw frame hex, the device-info packet
(raw hex + parsed fields), each reading packet (raw hex + parsed fields), and
rolling packet-timing statistics.

This is a *debugging* tool for inspecting what the meter actually sends — the
clean, console-friendly version of this app is ``examples/live.py`` (which
uses the shared ``brymen.console`` output helpers instead).

Without a MAC, the debug stream scans for the first BM78xBT meter it finds.

Usage:
    python examples/debug_stream.py [MAC] [PASSWORD]

Examples:
    python examples/debug_stream.py               # scan, then connect to the first meter
    python examples/debug_stream.py 00:11:22:33:44:55 1234
"""
import asyncio
import sys
from typing import Optional

from bleak import BleakError

import display
from brymen import (
    DEFAULT_PASSWORD, BrymenClient, CommandError, console, find_first_meter,
)

# Connection / reconnect policy.
SCAN_TIMEOUT = 5      # seconds to scan for a meter when no MAC is given
CONNECT_TIMEOUT = 5      # seconds to wait for a single connect attempt
RETRY_INTERVAL = 5        # seconds between reconnect attempts
MAX_RETRIES = 3           # max reconnect attempts before giving up
LINK_DOWN_GRACE = 2       # extra seconds to confirm a link drop before reconnecting


async def connect_client(mac: str, password: str) -> BrymenClient:
    """Create a client and connect it, applying the retry policy."""
    client = BrymenClient(
        mac, password, connect_timeout=CONNECT_TIMEOUT,
        sync_rtc_on_connect=True,
    )
    await client.ensure_connected(
        retries=MAX_RETRIES, retry_interval=RETRY_INTERVAL, on_retry=console.retry,
    )
    return client


async def run_auto(client: BrymenClient):
    """Print each frame as it arrives; reconnects are handled by the SDK.

    ``BrymenClient.read_stream()`` owns the pause-vs-power-off decision: a
    data gap with the BLE link up is a function-switch pause (waited out, not
    reconnected); a link drop is confirmed with a grace window, then
    reconnected with the bounded retry policy above.
    """
    console.status("debug stream: printing raw frames as they arrive (Ctrl+C to quit)")

    async for frame in client.read_stream(
        link_down_grace=LINK_DOWN_GRACE,
        retries=MAX_RETRIES,
        retry_interval=RETRY_INTERVAL,
        on_retry=console.retry,
        on_lost=console.lost,
        on_reconnected=console.reconnected,
    ):
        display.print_frame(frame)


async def scan_for_meter(timeout: float = SCAN_TIMEOUT) -> str:
    """Scan for the first BM78xBT meter and return its MAC address."""
    console.scanning()
    meter = await find_first_meter(timeout=timeout, retry_interval=0)
    if meter is None:
        raise ConnectionError(
            "No BM78xBT meters found — power the meter on and retry, or "
            "pass its MAC address explicitly."
        )
    console.found(meter.address, meter.name, meter.rssi)
    return meter.address


async def main(mac: Optional[str], password: str):
    if mac is None:
        mac = await scan_for_meter()
    console.connecting(mac)
    client = await connect_client(mac, password)
    try:
        console.connected(mac, detail="subscribed; listening for data")
        await run_auto(client)
    finally:
        await client.close()
    console.disconnected()


def parse_args(argv):
    mac = None  # None -> auto-scan for a meter
    password = DEFAULT_PASSWORD
    for arg in argv:
        if ":" in arg:  # likely a MAC
            mac = arg
        elif arg.isdigit() and len(arg) == 4:
            password = arg
    return mac, password


if __name__ == "__main__":
    mac, password = parse_args(sys.argv[1:])
    try:
        sys.exit(asyncio.run(main(mac, password)))
    except KeyboardInterrupt:
        print("\nProgram terminated.")
        sys.exit(130)
    except (ConnectionError, CommandError, BleakError) as exc:
        # No traceback for expected failures (reconnect exhausted, bad
        # password, ...) — just a clean one-line message.
        print(f"Error: {exc}")
        sys.exit(1)
