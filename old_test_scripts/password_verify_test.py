import asyncio
from bleak import BleakClient

COMMAND_CHAR_UUID = "0003cdd4-0000-1000-8000-00805f9b0131"

def calculate_crc(data: bytes) -> bytes:
    """
    Python implementation of the CRC16-reverse algorithm from the manual.
    Polynomial x16+x15+x2+1 (0x8005) -> reversed 0xA001.
    """
    reg_crc = 0xFFFF
    for byte in data:
        reg_crc ^= byte
        for _ in range(8):
            if reg_crc & 0x01:
                reg_crc = (reg_crc >> 1) ^ 0xA001
            else:
                reg_crc >>= 1
    # The manual indicates Checksum0 then Checksum1, which is little-endian
    return reg_crc.to_bytes(2, byteorder='little')

def build_command_packet(mac_address: str, command_id: bytes, args: bytes) -> bytes:
    # Remove colons and convert MAC to bytes
    mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
    
    # NOTE: If this still throws Error 0x01, remove the [::-1] to send MAC in standard order
    mac_bytes_reversed = mac_bytes[::-1] 

    # Build Header (Indices 0 - 1)
    header = bytes([0xFF, 0x01])
    
    # Build Payload (Indices 2 - 27 for CRC calculation)
    payload_length = bytes([0x20])
    packet_type = bytes([0x01])
    protocol_version = bytes([0x01])
    password_id = bytes([0x01])
    
    # Ensure args is exactly 14 bytes (Arg0 to Arg13)
    args = args.ljust(14, b'\x00')
    
    # Assemble the payload segment to be hashed
    payload = (
        payload_length + 
        packet_type + 
        protocol_version + 
        mac_bytes_reversed + 
        command_id + 
        password_id + 
        args
    )
    
    # Calculate CRC on bytes [2] ~ [27]
    crc_bytes = calculate_crc(payload)
    
    # Build Footer (Indices 30 - 31)
    footer = bytes([0xFF, 0x03])
    
    # Return full 32-byte packet
    return header + payload + crc_bytes + footer

async def send_command(mac_address: str, packet: bytes):
    async with BleakClient(mac_address) as client:
        print(f"Connected to {mac_address}")
        
        await client.write_gatt_char(COMMAND_CHAR_UUID, packet, response=True)
        print("Packet written, waiting for response...")
        
        await asyncio.sleep(0.5)
        
        response = await client.read_gatt_char(COMMAND_CHAR_UUID)
        spaced = ' '.join(f"{b:02X}" for b in response)
        print(f"Response ({len(response)} bytes): {spaced}")
        return response

async def main():
    target_mac = "00:11:22:33:44:55"
    
    # Command 0x0151 (Verify Password). Little-endian bytes: 0x51, 0x01
    cmd_verify_password = bytes([0x51, 0x01])
    
    # Use four zero bytes for the password (was ASCII '0000' which caused Error 3)
    password_args = bytes([0x00, 0x00, 0x00, 0x00])
    
    packet = build_command_packet(target_mac, cmd_verify_password, password_args)
    
    spaced_packet = ' '.join(f"{b:02X}" for b in packet)
    print(f"Sending packet: {spaced_packet}")
    
    try:
        await send_command(target_mac, packet)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())