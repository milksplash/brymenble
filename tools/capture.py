"""
Capture real frames from a BM78xBT meter as pytest fixtures.

Works like main.py's manual mode:
    connect -> authenticate -> subscribe -> press Enter to grab the latest frame.

After each capture you type:
    1. the GROUND TRUTH display value (exactly what the meter shows), and
    2. an optional note (e.g. "R1 auto" / "DCV manual").

Captures append to tests/fixtures/captures.json. The pytest suite
(tests/test_real_captures.py) then asserts each frame parses to the recorded
ground truth.

NOTE: captured frames contain the meter's MAC address (info packet bytes 6-11).
Fine for local git; strip it if you ever publish the repo.

Usage:
    .venv\\Scripts\\python.exe tools\\capture.py [MAC] [PASSWORD]
"""
import asyncio
import json
import os
import sys
from datetime import datetime

# Allow running directly as `python tools\\capture.py` from anywhere in the repo:
# running a script by path puts only its own directory on sys.path, so add the
# SDK source directory (repo/src) to find the brymen package.
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
))

from bleak import BleakClient

from brymen import commands

COMMAND_CHAR_UUID = "0003cdd4-0000-1000-8000-00805f9b0131"
NOTIFY_CHAR_UUID = "0003cdd5-0000-1000-8000-00805f9b0131"
DEFAULT_PASSWORD = "0000"
DEFAULT_MAC = "00:11:22:33:44:55"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(ROOT, "tests", "fixtures")
FIXTURES_FILE = os.path.join(FIXTURES_DIR, "captures.json")

latest_frame = None  # most recently received 152-byte frame


def notification_handler(sender: int, data: bytearray):
    global latest_frame
    latest_frame = bytes(data)


def load_captures():
    if os.path.exists(FIXTURES_FILE):
        with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_captures(captures):
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    with open(FIXTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(captures, f, indent=2, ensure_ascii=False)


async def capture_loop(mac_address: str, password: str):
    global latest_frame

    captures = load_captures()
    auth_packet = commands.build_verify_password_packet(mac_address, password)

    async with BleakClient(mac_address) as client:
        print(f"Connected to {mac_address}")
        print("Authenticating...")
        await client.write_gatt_char(COMMAND_CHAR_UUID, auth_packet, response=True)
        await asyncio.sleep(0.5)

        await client.start_notify(NOTIFY_CHAR_UUID, notification_handler)
        print("Listening... Press Enter to capture the current frame (Ctrl+C to quit).\n")

        while True:
            await asyncio.to_thread(input, ">> press Enter to capture: ")
            if latest_frame is None:
                print("   (no frame received yet)")
                continue
            if len(latest_frame) != 152:
                print(f"   (unexpected frame length {len(latest_frame)} - skipped)")
                continue

            expected = await asyncio.to_thread(
                input, "   ground truth (exactly what the meter shows, e.g. '10.02 MΩ'): ")
            expected = expected.strip()
            note = await asyncio.to_thread(
                input, "   note (function/range, e.g. 'R1 auto' - optional): ")
            note = note.strip()

            number = len(captures) + 1
            captures.append({
                "name": f"cap-{number:03d}",
                "expected": expected,
                "note": note,
                "hex": latest_frame.hex().upper(),
                "captured_at": datetime.now().isoformat(timespec="seconds"),
            })
            save_captures(captures)
            print(f"   saved cap-{number:03d}  ({len(captures)} total)\n")
            latest_frame = None  # require a fresh frame next time


if __name__ == "__main__":
    mac = DEFAULT_MAC
    pwd = DEFAULT_PASSWORD
    for arg in sys.argv[1:]:
        if ":" in arg:
            mac = arg
        elif arg.isdigit() and len(arg) == 4:
            pwd = arg

    try:
        asyncio.run(capture_loop(mac, pwd))
    except KeyboardInterrupt:
        print("\nDone. Captures saved to tests/fixtures/captures.json")
