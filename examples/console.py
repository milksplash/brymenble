"""Sample console app for the brymenble SDK.

Connects to a Brymen BM78xBT multimeter over BLE and streams its readings to
the console continuously as they arrive.

Without a MAC, the console scans for the first BM78xBT meter it finds.

Usage:
    python examples/console.py [MAC] [PASSWORD]

Examples:
    python examples/console.py               # scan, then connect to the first meter
    python examples/console.py 00:11:22:33:44:55 1234
"""
import asyncio
import sys
from typing import Optional

from bleak import BleakError

import display
from brymen import DEFAULT_PASSWORD, BrymenClient, CommandError, find_first_meter

# Connection / reconnect policy.
SCAN_TIMEOUT = 5      # seconds to scan for a meter when no MAC is given
CONNECT_TIMEOUT = 5      # seconds to wait for a single connect attempt
RETRY_INTERVAL = 5        # seconds between reconnect attempts
MAX_RETRIES = 3           # max reconnect attempts before giving up
NO_DATA_TIMEOUT = 3       # seconds without a frame before checking link state
LINK_DOWN_GRACE = 2       # extra seconds to confirm a link drop before reconnecting


def _on_retry(attempt: int, max_retries: int, error: Exception) -> None:
    """Progress callback for BrymenClient.ensure_connected()."""
    print(f"Connection attempt {attempt}/{max_retries} failed: {error}")


async def connect_client(mac: str, password: str) -> BrymenClient:
    """Create a client and connect it, applying the retry policy."""
    client = BrymenClient(
        mac, password, connect_timeout=CONNECT_TIMEOUT,
        sync_rtc_on_connect=True,
    )
    await client.ensure_connected(
        retries=MAX_RETRIES, retry_interval=RETRY_INTERVAL, on_retry=_on_retry,
    )
    return client


async def run_auto(client: BrymenClient):
    """Print each frame as it arrives; reconnects are handled by the SDK.

    ``BrymenClient.read_stream()`` owns the pause-vs-power-off decision: a
    data gap with the BLE link up is a function-switch pause (waited out, not
    reconnected); a link drop is confirmed with a grace window, then
    reconnected with the bounded retry policy above.
    """
    print("Auto mode: readings will appear as they arrive. (Ctrl+C to quit)")

    def _on_pause() -> None:
        print(f"No data for {NO_DATA_TIMEOUT}s but BLE link still up — "
              "meter paused (e.g. function switch). Waiting...")

    def _on_lost(reason: str) -> None:
        print("BLE link lost — meter powered off. Reconnecting...")

    def _on_reconnected() -> None:
        print("Reconnected and re-subscribed.")

    async for frame in client.read_stream(
        no_data_timeout=NO_DATA_TIMEOUT,
        link_down_grace=LINK_DOWN_GRACE,
        retries=MAX_RETRIES,
        retry_interval=RETRY_INTERVAL,
        on_retry=_on_retry,
        on_pause=_on_pause,
        on_lost=_on_lost,
        on_reconnected=_on_reconnected,
    ):
        display.print_frame(frame.info, frame.readings)


async def scan_for_meter(timeout: float = SCAN_TIMEOUT) -> str:
    """Scan for the first BM78xBT meter and return its MAC address."""
    print(f"Scanning for BM78xBT meters ({timeout:.0f}s)...")
    meter = await find_first_meter(timeout=timeout, retry_interval=0)
    if meter is None:
        raise ConnectionError(
            "No BM78xBT meters found — power the meter on and retry, or "
            "pass its MAC address explicitly."
        )
    name = f" ({meter.name})" if meter.name else ""
    print(f"Found {meter.address}{name}, rssi={meter.rssi}.")
    return meter.address


async def main(mac: Optional[str], password: str):
    if mac is None:
        mac = await scan_for_meter()
    print(f"Connecting to {mac}...")
    client = await connect_client(mac, password)
    try:
        print(f"Connected to {mac} and subscribed. Listening for data...")
        await run_auto(client)
    finally:
        await client.close()
    print("Disconnected.")


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
