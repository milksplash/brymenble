# Parsing of Device Information and Device Reading packets

from dataclasses import dataclass
import struct
from typing import List, Optional, Tuple

from . import constants
from . import crc


@dataclass(frozen=True)
class RtcTime:
    """Decoded RTC time-of-day from a reading packet (bytes 8..13)."""
    year: int
    month: int
    date: int
    hour: int
    minute: int
    second: int
    millisecond: int


@dataclass(frozen=True)
class InfoPacket:
    """Parsed Device Information packet (24 bytes)."""
    device_category: int
    mac: bytes
    battery_status: int
    power_source: int
    reading_packet_count: int
    device_reading_pk_no: int
    crc_ok: bool
    raw: bytes

    @property
    def category_name(self) -> str:
        """Human-readable device category, e.g. 'Multimeter'."""
        return constants.CATEGORY_NAMES.get(
            self.device_category, f"0x{self.device_category:02X}"
        )

    @property
    def battery_name(self) -> str:
        """Human-readable battery status, e.g. 'Normal'."""
        return constants.BATTERY_NAMES.get(
            self.battery_status, f"0x{self.battery_status:02X}"
        )

    @property
    def mac_str(self) -> str:
        """MAC address as 'XX:XX:XX:XX:XX:XX'."""
        return ':'.join(f'{b:02X}' for b in self.mac)


@dataclass(frozen=True)
class ReadingPacket:
    """Parsed Device Reading packet (32 bytes)."""
    function_name: str
    unit: str
    raw_value: int
    decimal_pos: int
    prefix: str
    display_digit_count: int
    status0: int
    status1: int
    rtc: RtcTime
    is_overload: bool
    is_ascii: bool
    ascii_text: Optional[str]
    crc_ok: bool
    raw: bytes


def parse_info_packet(packet: bytes) -> Optional[InfoPacket]:
    """
    Parse a 24-byte Device Information Packet into an InfoPacket.
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

    return InfoPacket(
        device_category=packet[5],
        # The meter sends the MAC byte-reversed on the wire (same order the
        # command packet builder expects); store it in display order.
        mac=packet[6:12][::-1],
        battery_status=packet[12],
        power_source=packet[13],
        reading_packet_count=packet[16],
        device_reading_pk_no=packet[19],
        crc_ok=crc_ok,
        raw=packet,
    )


def parse_rtc_from_packet(packet: bytes) -> RtcTime:
    """
    Decode RTC time from bytes 8..13 of the reading packet into an RtcTime.
    """
    if len(packet) < 14:
        return RtcTime(0, 0, 0, 0, 0, 0, 0)

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
    # Hour: 5 bits = byte10 bits 7..6 (LOW 2) + byte11 bits 2..0 (HIGH 3).
    # Verified against hardware: a stored hour of 20 (0b10100) was previously
    # misread as 5 (0b00101) when the halves were assumed the other way round.
    hour = ((b10 >> 6) & 0x03) | ((b11 & 0x07) << 2)
    # Minute: byte10 bits 5..0
    minute = b10 & 0x3F
    # Second: byte9 bits 7..2
    second = (b9 >> 2) & 0x3F
    # Millisecond: byte9 bits 1..0 + byte8 bits 7..0 (10 bits)
    millisecond = ((b9 & 0x03) << 8) | b8

    return RtcTime(year, month, date, hour, minute, second, millisecond)


def parse_reading_packet(packet: bytes) -> Optional[ReadingPacket]:
    """
    Parse a 32-byte Device Reading Packet into a ReadingPacket.
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

    return ReadingPacket(
        function_name=function_name,
        unit=unit,
        raw_value=raw_value,
        decimal_pos=decimal_pos,
        prefix=prefix,
        display_digit_count=display_digits,
        status0=status0,
        status1=status1,
        rtc=rtc,
        is_overload=is_overload,
        is_ascii=is_ascii,
        ascii_text=ascii_text,
        crc_ok=crc_ok,
        raw=packet,
    )


def parse_stream_frame(data: bytes) -> Tuple[Optional[InfoPacket], List[Optional[ReadingPacket]]]:
    """
    Split a full 152-byte notification frame into its info packet and reading
    packets, then parse each.

    Returns (info, readings):
        info     - parsed InfoPacket, or None if the frame has an unexpected
                   size (or its info packet is invalid).
        readings - list of parsed ReadingPackets; entries are None for empty /
                   invalid reading packets (the 3 trailing packets are normally
                   all-zero and come back None).
    """
    if len(data) != constants.STREAM_FRAME_LENGTH:
        print(f"Unexpected frame length: {len(data)}")
        return None, None

    info_data = data[:constants.INFO_PACKET_LENGTH]
    reading_data = [
        data[constants.INFO_PACKET_LENGTH + i * constants.READING_PACKET_LENGTH:
             constants.INFO_PACKET_LENGTH + (i + 1) * constants.READING_PACKET_LENGTH]
        for i in range(constants.READINGS_PER_FRAME)
    ]

    info = parse_info_packet(info_data)
    readings = [parse_reading_packet(pkt) for pkt in reading_data]
    return info, readings


@dataclass(frozen=True)
class CommandResponse:
    """Parsed 32-byte command/response packet (protocol spec section 2)."""

    command_id: int       # echoed command ID, or 0x8001 for a failure frame
    args: bytes           # Arg[0..13] (14 bytes)
    crc_ok: bool

    @property
    def is_failure(self) -> bool:
        """True if this is a 0x8001 failure frame."""
        return self.command_id == constants.CMD_FAILURE

    @property
    def failing_command_id(self) -> Optional[int]:
        """Failure frames: the command that failed (Arg[0:2], little-endian)."""
        if not self.is_failure or len(self.args) < 4:
            return None
        return self.args[0] | (self.args[1] << 8)

    @property
    def error_code(self) -> Optional[int]:
        """Failure frames: the meter error code (Arg[2:4], little-endian)."""
        if not self.is_failure or len(self.args) < 4:
            return None
        return self.args[2] | (self.args[3] << 8)

    def error_message(self) -> Optional[str]:
        """Human-readable message for failure frames, or None."""
        if self.error_code is None:
            return None
        return constants.ERROR_CODES.get(
            self.error_code, f"Unknown error {self.error_code}"
        )


def parse_command_response(packet: bytes) -> Optional[CommandResponse]:
    """Parse a 32-byte response packet (type 0x02). None if invalid."""
    if len(packet) != constants.COMMAND_PACKET_LENGTH:
        return None
    if packet[0] != constants.HEAD_BYTE0 or packet[1] != constants.COMMAND_HEAD_BYTE1:
        return None
    if packet[2] != constants.COMMAND_PACKET_LEN_BYTE:
        return None
    if packet[3] != constants.COMMAND_RESPONSE_TYPE:
        return None
    if packet[4] != constants.PROTOCOL_VERSION:
        return None

    crc_data = packet[constants.COMMAND_CRC_START:constants.COMMAND_CRC_END]
    expected_crc = struct.unpack('<H', packet[28:30])[0]
    crc_ok = crc.verify_crc(crc_data, expected_crc)

    command_id = packet[11] | (packet[12] << 8)
    return CommandResponse(command_id=command_id, args=packet[14:28], crc_ok=crc_ok)