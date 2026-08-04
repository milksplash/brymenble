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

import display
from brymen import DEFAULT_PASSWORD, BrymenClient

DEFAULT_MAC = "00:11:22:33:44:55"


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
    async with BrymenClient(mac, password) as client:
        print(f"Connected to {mac} and subscribed. Listening for data...")
        if manual:
            await run_manual(client)
        else:
            await run_auto(client)
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
