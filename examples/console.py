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
from brymen import DEFAULT_PASSWORD, BrymenClient, CommandError, find_meters

# Connection / reconnect policy.
SCAN_TIMEOUT = 5      # seconds to scan for a meter when no MAC is given
CONNECT_TIMEOUT = 5      # seconds to wait for a single connect attempt
RETRY_INTERVAL = 5        # seconds between reconnect attempts
MAX_RETRIES = 3           # max reconnect attempts before giving up
NO_DATA_TIMEOUT = 3       # seconds without a frame before treating the meter as off


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
    """Print each frame as it arrives, reconnecting if the meter goes silent."""
    print("Auto mode: readings will appear as they arrive. (Ctrl+C to quit)")
    while True:
        frame = await client.wait_frame(timeout=NO_DATA_TIMEOUT)
        if frame is None:
            print(f"No data for {NO_DATA_TIMEOUT}s — meter may be powered off. "
                  "Reconnecting...")
            await client.ensure_connected(
                retries=MAX_RETRIES, retry_interval=RETRY_INTERVAL,
                on_retry=_on_retry,
            )
            print("Reconnected and re-subscribed.")
            continue
        info, readings = frame
        display.print_frame(info, readings)


async def scan_for_meter(timeout: float = SCAN_TIMEOUT) -> str:
    """Scan for the first BM78xBT meter and return its MAC address."""
    print(f"Scanning for BM78xBT meters ({timeout:.0f}s)...")
    meters = await find_meters(timeout=timeout)
    if not meters:
        raise ConnectionError(
            "No BM78xBT meters found — power the meter on and retry, or "
            "pass its MAC address explicitly."
        )
    m = meters[0]
    name = f" ({m.name})" if m.name else ""
    print(f"Found {m.address}{name}, rssi={m.rssi}.")
    return m.address


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
