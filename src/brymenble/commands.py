"""Building of BM78xBT command packets (32 bytes, see protocol spec section 2)."""

from datetime import datetime
from typing import Optional, Union

from . import constants
from . import crc


def build_command_packet(
    mac_address: str, command_id: Union[int, bytes], args: bytes = b""
) -> bytes:
    """
    Build a 32-byte command packet.

    Args:
        mac_address: BLE device address as 'XX:XX:XX:XX:XX:XX'.
        command_id:  command ID as a 2-byte little-endian bytes value
                     (e.g. constants.CMD_VERIFY_PASSWORD) or as an int
                     (e.g. constants.CMD_RTC_TIME_CALIBRATION).
        args:        command-specific arguments (up to 14 bytes), zero-padded.

    Raises:
        ValueError: if mac_address is not a 6-byte address or command_id is
                    not a valid 2-byte ID.
    """
    mac_bytes = bytes.fromhex(mac_address.replace(':', ''))
    if len(mac_bytes) != 6:
        raise ValueError("MAC address must be 6 bytes")
    if isinstance(command_id, int):
        if not 0 <= command_id <= 0xFFFF:
            raise ValueError("command_id must be a 2-byte value (0-0xFFFF)")
        command_id = command_id.to_bytes(2, 'little')
    if len(command_id) != 2:
        raise ValueError("command_id must be exactly 2 bytes")
    if len(args) > 14:
        raise ValueError("args must be at most 14 bytes")

    header = bytes([constants.COMMAND_HEAD_BYTE0, constants.COMMAND_HEAD_BYTE1])
    payload = (
        bytes([
            constants.COMMAND_PACKET_LEN_BYTE,
            constants.COMMAND_PACKET_TYPE,
            constants.PROTOCOL_VERSION,
        ])
        + mac_bytes[::-1]  # BLE device address, reversed byte order
        + command_id
        + bytes([constants.PASSWORD_ID])
        + args.ljust(14, b'\x00')
    )
    crc_bytes = crc.calculate_crc(payload).to_bytes(2, 'little')
    footer = bytes([constants.COMMAND_END_BYTE0, constants.COMMAND_END_BYTE1])
    return header + payload + crc_bytes + footer


def build_verify_password_packet(mac_address: str, password: str = "0000") -> bytes:
    """Build a 'Verify Password' (0x0151) command packet."""
    if len(password) != 4 or not password.isdigit():
        raise ValueError("Password must be a 4-digit string")
    args = bytes(int(ch) for ch in password)
    return build_command_packet(mac_address, constants.CMD_VERIFY_PASSWORD, args)


def encode_rtc_time_args(when: datetime) -> bytes:
    """Encode a datetime as RTC Calibration (0x0010) args.

    Arg[0..6] = second, minute, hour, date, day-of-week (Mon=1..Sun=7),
    month, year-2000; Arg[7..13] zero (see protocol spec).
    """
    day_of_week = when.weekday() + 1        # Mon=1 .. Sun=7 (protocol range)
    return bytes([
        when.second, when.minute, when.hour, when.day,
        day_of_week, when.month, when.year - 2000,
    ]) + b'\x00' * 7


def build_rtc_time_packet(mac_address: str, when: Optional[datetime] = None) -> bytes:
    """Build an 'RTC Time Calibration' (0x0010) command packet.

    The meter has no RTC battery, so its clock resets on power-off and must be
    re-synced after connecting. Defaults to the host's local time.
    """
    if when is None:
        when = datetime.now()
    return build_command_packet(
        mac_address, constants.CMD_RTC_TIME_CALIBRATION, encode_rtc_time_args(when)
    )
