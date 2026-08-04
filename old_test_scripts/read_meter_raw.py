import asyncio
from bleak import BleakClient

COMMAND_CHAR_UUID = "0003cdd4-0000-1000-8000-00805f9b0131"
NOTIFY_CHAR_UUID = "0003cdd5-0000-1000-8000-00805f9b0131"

# --- Configuration ---
PASSWORD = "0000"
TARGET_MAC = "00:11:22:33:44:55"

# --- Helper Functions ---

def calculate_crc(data: bytes) -> bytes:
    reg_crc = 0xFFFF
    for byte in data:
        reg_crc ^= byte
        for _ in range(8):
            if reg_crc & 0x01:
                reg_crc = (reg_crc >> 1) ^ 0xA001
            else:
                reg_crc >>= 1
    return reg_crc.to_bytes(2, byteorder='little')

def build_command_packet(mac_address: str, command_id: bytes, args: str) -> bytes:
    mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
    mac_bytes_reversed = mac_bytes[::-1] 

    header = bytes([0xFF, 0x01])
    payload_length = bytes([0x20])
    packet_type = bytes([0x01])
    protocol_version = bytes([0x01])
    password_id = bytes([0x01])
    
    if len(args) != 4 or not args.isdigit():
        raise ValueError("PASSWORD must be a 4-digit string")
    args_bytes = bytes(int(ch) for ch in args)
    args_bytes = args_bytes.ljust(14, b'\x00')
    
    payload = (
        payload_length + packet_type + protocol_version + 
        mac_bytes_reversed + command_id + password_id + args_bytes
    )
    
    crc_bytes = calculate_crc(payload)
    footer = bytes([0xFF, 0x03])
    
    return header + payload + crc_bytes + footer

# --- Simplified Notification Handler ---

def format_hex(data: bytes) -> str:
    return ' '.join(f"{b:02X}" for b in data)


def notification_handler(sender: int, data: bytearray):
    """
    Prints the raw notification, but omits the trailing empty reading packets.
    """
    if len(data) == 152 and data[0:2] == b'\xFF\x01' and data[3] == 0x04:
        info_packet = data[:24]
        first_reading_packet = data[24:56]
        print(f"Notify [152 bytes]: Device info + first reading only")
        print(f"  Info Packet: {format_hex(info_packet)}")
        print(f"  Reading Packet: {format_hex(first_reading_packet)}")
    else:
        raw_hex = format_hex(data)
        print(f"Notify [{len(data)} bytes]: {raw_hex}")

# --- Main Async Loop ---

async def monitor_meter(mac_address: str):
    # 1. Build Verification Packet
    cmd_verify_password = bytes([0x51, 0x01])
    auth_packet = build_command_packet(mac_address, cmd_verify_password, PASSWORD)

    async with BleakClient(mac_address) as client:
        print(f"Connected to {mac_address}")
        
        # 2. Authenticate to unlock the data stream
        print("Authenticating...")
        auth_hex = ' '.join(f"{b:02X}" for b in auth_packet)
        print(f"Write auth packet ({len(auth_packet)} bytes): {auth_hex}")
        await client.write_gatt_char(COMMAND_CHAR_UUID, auth_packet, response=True)
        await asyncio.sleep(0.5) 
        
        # 3. Subscribe to Data Stream
        print(f"Subscribing to notifications on {NOTIFY_CHAR_UUID}...")
        await client.start_notify(NOTIFY_CHAR_UUID, notification_handler)
        
        print("Listening for raw data... (Press Ctrl+C to stop)")
        
        # 4. Keep the script running to catch notifications
        try:
            while True:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        finally:
            await client.stop_notify(NOTIFY_CHAR_UUID)

if __name__ == "__main__":
    try:
        asyncio.run(monitor_meter(TARGET_MAC))
    except KeyboardInterrupt:
        print("\nProgram terminated.")