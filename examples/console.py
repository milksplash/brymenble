"""Sample console app for the brymenble SDK.

Connects to a Brymen BM78xBT multimeter over BLE and streams its readings to
the console continuously as they arrive.

Usage:
    python examples/console.py [MAC] [PASSWORD]

Examples:
    python examples/console.py
    python examples/console.py 00:11:22:33:44:55 1234
"""
import asyncio
import sys
from typing import Optional

from bleak import BleakError

import display
from brymen import DEFAULT_PASSWORD, BrymenClient, CommandError

# Synthetic placeholder; the owner's real meter MAC was scrubbed from tracked
# files but remains in git history — purge it (e.g. `git filter-repo`) before
# publishing the repo.
DEFAULT_MAC = "00:11:22:33:44:55"

# Connection / reconnect policy.
CONNECT_TIMEOUT = 5      # seconds to wait for a single connect attempt
RETRY_INTERVAL = 5        # seconds between reconnect attempts
MAX_RETRIES = 3           # max reconnect attempts before giving up
NO_DATA_TIMEOUT = 3       # seconds without a frame before treating the meter as off


async def ensure_connected(
    client: Optional[BrymenClient], mac: str, password: str
) -> BrymenClient:
    """Connect a new client, or reconnect an existing one, applying the retry
    policy (RETRY_INTERVAL between attempts, MAX_RETRIES max). Returns a
    connected client (the same object when one was already passed in)."""
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if client is None:
                client = BrymenClient(
                    mac, password, connect_timeout=CONNECT_TIMEOUT,
                    sync_rtc_on_connect=True,
                )
                await client.__aenter__()
            else:
                await client.reconnect()
            return client
        except (ConnectionError, asyncio.TimeoutError, BleakError) as exc:
            last_error = exc
            print(f"Connection attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                print(f"Retrying in {RETRY_INTERVAL}s...")
                await asyncio.sleep(RETRY_INTERVAL)
    raise ConnectionError(
        f"Could not connect to {mac} after {MAX_RETRIES} attempts "
        f"(last error: {last_error})"
    ) from last_error


async def run_auto(client: BrymenClient, mac: str, password: str):
    """Print each frame as it arrives, reconnecting if the meter goes silent."""
    print("Auto mode: readings will appear as they arrive. (Ctrl+C to quit)")
    while True:
        frame = await client.wait_frame(timeout=NO_DATA_TIMEOUT)
        if frame is None:
            print(f"No data for {NO_DATA_TIMEOUT}s — meter may be powered off. "
                  "Reconnecting...")
            client = await ensure_connected(client, mac, password)
            print("Reconnected and re-subscribed.")
            continue
        info, readings = frame
        display.print_frame(info, readings)


async def main(mac: str, password: str):
    print(f"Connecting to {mac}...")
    client = await ensure_connected(None, mac, password)
    try:
        print(f"Connected to {mac} and subscribed. Listening for data...")
        await run_auto(client, mac, password)
    finally:
        await client.__aexit__(None, None, None)
    print("Disconnected.")


def parse_args(argv):
    mac = DEFAULT_MAC
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
    except (ConnectionError, CommandError) as exc:
        # No traceback for expected failures (reconnect exhausted, bad
        # password, ...) — just a clean one-line message.
        print(f"Error: {exc}")
        sys.exit(1)
