# crc.py
# CRC-16 (Reverse, polynomial 0xA001) calculation and verification

def calculate_crc(data: bytes) -> int:
    """Return CRC-16 (little-endian) over the given bytes."""
    reg_crc = 0xFFFF
    for byte in data:
        reg_crc ^= byte
        for _ in range(8):
            if reg_crc & 0x01:
                reg_crc = (reg_crc >> 1) ^ 0xA001
            else:
                reg_crc >>= 1
    return reg_crc

def verify_crc(data: bytes, expected_crc: int) -> bool:
    """Check if the CRC of 'data' matches 'expected_crc'."""
    return calculate_crc(data) == expected_crc