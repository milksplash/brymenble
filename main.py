import asyncio
import sys
from bleak import BleakClient

import constants
import crc
import parsers
import display

COMMAND_CHAR_UUID = "0003cdd4-0000-1000-8000-00805f9b0131"
NOTIFY_CHAR_UUID = "0003cdd5-0000-1000-8000-00805f9b0131"

DEFAULT_PASSWORD = "0000"

frame_queue = asyncio.Queue(maxsize=1)   # stores (info, readings) or None
auto_print = True                        # default auto mode unless manual is requested


def build_command_packet(mac_address: str, command_id: bytes, args: str) -> bytes:
    mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
    mac_bytes_reversed = mac_bytes[::-1]
    header = bytes([0xFF, 0x01])
    payload_length = bytes([0x20])
    packet_type = bytes([0x01])
    protocol_version = bytes([0x01])
    password_id = bytes([0x01])

    if len(args) != 4 or not args.isdigit():
        raise ValueError("Password must be a 4-digit string")
    args_bytes = bytes(int(ch) for ch in args)
    args_bytes = args_bytes.ljust(14, b'\x00')

    payload = (
        payload_length + packet_type + protocol_version +
        mac_bytes_reversed + command_id + password_id + args_bytes
    )
    crc_bytes = crc.calculate_crc(payload).to_bytes(2, 'little')
    footer = bytes([0xFF, 0x03])
    return header + payload + crc_bytes + footer


def notification_handler(sender: int, data: bytearray):
    info, readings = parsers.parse_stream_frame(bytes(data))
    if info is None:
        return
    # Overwrite previous frame (we only keep the latest)
    try:
        frame_queue.put_nowait((info, readings))
    except asyncio.QueueFull:
        # Replace the old frame with the new one
        frame_queue.get_nowait()
        frame_queue.put_nowait((info, readings))


async def monitor_meter(mac_address: str, password: str = DEFAULT_PASSWORD):
    global auto_print

    cmd_verify_password = bytes([0x51, 0x01])
    auth_packet = build_command_packet(mac_address, cmd_verify_password, password)

    async with BleakClient(mac_address) as client:
        print(f"Connected to {mac_address}")
        print("Authenticating...")
        await client.write_gatt_char(COMMAND_CHAR_UUID, auth_packet, response=True)
        await asyncio.sleep(0.5)

        print(f"Subscribing to notifications on {NOTIFY_CHAR_UUID}...")
        await client.start_notify(NOTIFY_CHAR_UUID, notification_handler)
        print("Listening for data...")

        # Ensure notifications are stopped when we exit this listening block
        try:
            if auto_print:
                print("Auto‑print mode: readings will appear as they arrive.")
                try:
                    while True:
                        info, readings = await frame_queue.get()
                        display.print_frame(info, readings)
                except asyncio.CancelledError:
                    pass
            else:
                print("Manual mode: press Enter to show the latest reading (Ctrl+C to quit).")
                try:
                    while True:
                        # Wait for Enter (non‑blocking)
                        await asyncio.to_thread(input)
                        # Get the latest frame (if any)
                        if frame_queue.empty():
                            print("No data received yet.")
                        else:
                            # We only want the most recent; clear the queue and get the last one
                            latest = None
                            while not frame_queue.empty():
                                latest = frame_queue.get_nowait()
                            if latest is not None:
                                info, readings = latest
                                display.print_frame(info, readings)
                except asyncio.CancelledError:
                    pass
                except KeyboardInterrupt:
                    pass
        finally:
            await client.stop_notify(NOTIFY_CHAR_UUID)


if __name__ == "__main__":
    mac = "00:11:22:33:44:55" # My own meter's MAC address, remove before sharing code publicly
    pwd = DEFAULT_PASSWORD
    # Parse command line: python main.py MAC [PASSWORD] [--manual]
    args = sys.argv[1:]
    for arg in args:
        if arg.startswith('--manual') or arg == '-m':
            auto_print = False
        elif ':' in arg:   # likely a MAC
            mac = arg
        elif arg.isdigit() and len(arg) == 4:
            pwd = arg

    if mac is None:
        print("Usage: python main.py MAC [PASSWORD] [--manual]")
        sys.exit(1)

    try:
        asyncio.run(monitor_meter(mac, pwd))
    except KeyboardInterrupt:
        print("\nProgram terminated.")