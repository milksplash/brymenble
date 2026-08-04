# Parsing of Device Information and Device Reading packets

import struct
from typing import Dict, Optional

import constants
import crc


def parse_info_packet(packet: bytes) -> Optional[Dict]:
    """
    Parse a 24-byte Device Information Packet.
    Returns a dict with keys:
        device_category, mac, battery_status, power_source,
        reading_packet_count, device_reading_pk_no, crc_ok, raw
    Returns None if packet is invalid (wrong header, length, etc.).
    """
    if len(packet) != constants.INFO_PACKET_LENGTH:
        return None
    if packet[0] != constants.HEAD_BYTE0 or packet[1] != constants.HEAD_BYTE1_INFO:
        return None
    if packet[2] != constants.INFO_PACKET_LENGTH:
        return None
    if packet[3] != constants.INFO_PACKET_TYPE or packet[4] != constants.PROTOCOL_VERSION:
        return None

    # Verify CRC over bytes 2..19
    crc_data = packet[constants.INFO_CRC_START:constants.INFO_CRC_END]
    expected_crc = struct.unpack('<H', packet[constants.INFO_CRC_END:constants.INFO_CRC_END + 2])[0]
    crc_ok = crc.verify_crc(crc_data, expected_crc)

    return {
        'device_category': packet[5],
        'mac': packet[6:12],
        'battery_status': packet[12],
        'power_source': packet[13],
        'reading_packet_count': packet[16],
        'device_reading_pk_no': packet[19],
        'crc_ok': crc_ok,
        'raw': packet.hex()
    }


def parse_rtc_from_packet(packet: bytes) -> Dict:
    """
    Decode RTC time from bytes 8..13 of the reading packet.
    Returns dict with year, month, date, hour, minute, second, millisecond.
    """
    if len(packet) < 14:
        return {}

    b8 = packet[8]
    b9 = packet[9]
    b10 = packet[10]
    b11 = packet[11]
    b12 = packet[12]
    b13 = packet[13]

    # Date fields (bytes 12..13)
    # Year: byte13 bits 7..1 (2000 + value)
    year = 2000 + ((b13 >> 1) & 0x7F)
    # Month: byte13 bit0 + byte12 bits 7..5
    month = ((b13 & 0x01) << 3) | ((b12 >> 5) & 0x07)
    # Date: byte12 bits 4..0
    date = b12 & 0x1F

    # Time-of-day fields (bytes 8..11)
    # Hour: byte11 bits 2..0 + byte10 bits 7..6 (5 bits)
    hour = (b11 & 0x07) | (((b10 >> 6) & 0x03) << 3)
    # Minute: byte10 bits 5..0
    minute = b10 & 0x3F
    # Second: byte9 bits 7..2
    second = (b9 >> 2) & 0x3F
    # Millisecond: byte9 bits 1..0 + byte8 bits 7..0 (10 bits)
    millisecond = ((b9 & 0x03) << 8) | b8

    return {
        'year': year,
        'month': month,
        'date': date,
        'hour': hour,
        'minute': minute,
        'second': second,
        'millisecond': millisecond,
    }


def parse_reading_packet(packet: bytes) -> Optional[Dict]:
    """
    Parse a 32-byte Device Reading Packet.
    Returns a dict with fields:
        function_name, unit, raw_value, decimal_pos,
        prefix, display_digit_count,
        status0, status1, rtc, is_overload, is_ascii,
        ascii_text, crc_ok, raw
    Returns None if packet is invalid.
    """
    if len(packet) != constants.READING_PACKET_LENGTH:
        return None
    if packet[0] != constants.HEAD_BYTE0 or packet[1] != constants.HEAD_BYTE1_READING:
        return None
    if packet[2] != constants.READING_PACKET_LENGTH:
        return None
    if packet[3] != constants.READING_PACKET_TYPE:
        return None

    # Verify CRC over bytes 2..27
    crc_data = packet[constants.READING_CRC_START:constants.READING_CRC_END]
    expected_crc = struct.unpack('<H', packet[constants.READING_CRC_END:constants.READING_CRC_END + 2])[0]
    crc_ok = crc.verify_crc(crc_data, expected_crc)

    # Decode RTC from bytes 8..13
    rtc = parse_rtc_from_packet(packet)

    # Status flags (bytes 14, 15, 16)
    status0 = packet[14]
    status1 = packet[15]
    # status2 = packet[16]   # don't care

    # Function IDs (main and sub)
    main_id = packet[18]
    sub_id = packet[20]
    function_name = constants.FUNCTION_NAMES.get(
        (main_id, sub_id),
        f"Unknown({main_id:02X},{sub_id:02X})"
    )

    # Reading value (24‑bit signed integer, little-endian)
    raw_value = int.from_bytes(packet[21:24], byteorder='little', signed=True)

    # Decimal point position
    decimal_pos = packet[24]

    # Metrics prefix (signed byte)
    prefix_code = packet[25]
    if prefix_code >= 128:   # signed value
        prefix_code -= 256
    prefix = constants.PREFIX_MAP.get(prefix_code, "?")

    # Unit code
    unit_code = packet[26]
    unit = constants.UNIT_CODES.get(unit_code, f"0x{unit_code:02X}")

    # Display digit count
    display_digits = packet[27]

    # Special flags
    is_overload = bool(status1 & constants.STATUS1_OL)
    is_ascii = bool(status0 & constants.STATUS0_ASCII_READING)

    # If ASCII flag set, map raw_value to a display string
    ascii_text = None
    if is_ascii:
        ascii_text = constants.ASCII_READING_MAP.get(raw_value, f"0x{raw_value:06X}")

    return {
        'function_name': function_name,
        'unit': unit,
        'raw_value': raw_value,
        'decimal_pos': decimal_pos,
        'prefix': prefix,
        'display_digit_count': display_digits,
        'status0': status0,
        'status1': status1,
        'rtc': rtc,
        'is_overload': is_overload,
        'is_ascii': is_ascii,
        'ascii_text': ascii_text,
        'crc_ok': crc_ok,
        'raw': packet.hex(), # For debugging
    }