"""Sample console app for the brymenble SDK.

Connects to a Brymen BM78xBT multimeter over BLE and shows its readings on the
console, either continuously (auto mode) or on demand (manual mode).

Usage:
    python examples/console.py [MAC] [PASSWORD] [--manual]

Examples:
    python examples/console.py
    python examples/console.py 00:11:22:33:44:55 1234
    python examples/console.py 00:11:22:33:44:55 --manual
"""
import asyncio
import sys

from bleak import BleakError

import display
from brymen import DEFAULT_PASSWORD, BrymenClient

# Synthetic placeholder; the owner's real meter MAC was scrubbed from tracked
# files but remains in git history — purge it (e.g. `git filter-repo`) before
# publishing the repo.
DEFAULT_MAC = "00:11:22:33:44:55"

# Connection / reconnect policy.
CONNECT_TIMEOUT = 10      # seconds to wait for a single connect attempt
RETRY_INTERVAL = 10       # seconds between reconnect attempts
MAX_RETRIES = 5           # max reconnect attempts before giving up


async def connect_with_retry(mac: str, password: str) -> BrymenClient:
    """Connect, retrying every RETRY_INTERVAL seconds up to MAX_RETRIES times.

    Returns an already-connected client on success; raises ConnectionError if
    every attempt fails.
    """
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = BrymenClient(mac, password, connect_timeout=CONNECT_TIMEOUT)
            await client.__aenter__()
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


async def run_auto(client: BrymenClient):
    """Print each frame as it arrives."""
    print("Auto mode: readings will appear as they arrive. (Ctrl+C to quit)")
    async for info, readings in client:
        display.print_frame(info, readings)


async def run_manual(client: BrymenClient):
    """Print the latest frame each time the user presses Enter."""
    print("Manual mode: press Enter to show the latest reading (Ctrl+C to quit).")
    while True:
        await asyncio.to_thread(input)
        frame = client.latest()
        if frame is None:
            print("No data received yet.")
        else:
            info, readings = frame
            display.print_frame(info, readings)


async def main(mac: str, password: str, manual: bool):
    print(f"Connecting to {mac}...")
    client = await connect_with_retry(mac, password)
    try:
        print(f"Connected to {mac} and subscribed. Listening for data...")
        if manual:
            await run_manual(client)
        else:
            await run_auto(client)
    finally:
        await client.__aexit__(None, None, None)
    print("Disconnected.")


def parse_args(argv):
    mac = DEFAULT_MAC
    password = DEFAULT_PASSWORD
    manual = False
    for arg in argv:
        if arg in ("--manual", "-m"):
            manual = True
        elif ":" in arg:  # likely a MAC
            mac = arg
        elif arg.isdigit() and len(arg) == 4:
            password = arg
    return mac, password, manual


if __name__ == "__main__":
    mac, password, manual = parse_args(sys.argv[1:])
    try:
        asyncio.run(main(mac, password, manual))
    except KeyboardInterrupt:
        print("\nProgram terminated.")
