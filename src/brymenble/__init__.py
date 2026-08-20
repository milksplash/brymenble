"""brymenble — unofficial, open-source SDK for the Brymen BM78xBT BLE multimeter.

Public API:

- ``BrymenbleClient``: connect/authenticate/subscribe and stream parsed frames
- ``parsers``: ``InfoPacket`` / ``ReadingPacket`` / ``RtcTime`` and parse helpers
- ``commands``: command-packet builders
- ``formatter``: turn a parsed reading into a display string
- ``console``: shared console output (status lines) for every consumer
- ``scanner``: find BM78xBT meters from their BLE advertising packets
- ``crc`` / ``constants``: protocol primitives
"""

from . import commands, console, constants, crc, formatter, parsers, scanner
from .commands import (
    build_command_packet,
    build_rtc_time_packet,
    build_verify_password_packet,
)
from .crc import calculate_crc, verify_crc
from .formatter import format_reading
from .parsers import (
    CommandResponse,
    InfoPacket,
    ReadingPacket,
    RtcTime,
    StreamFrame,
    parse_command_response,
    parse_info_packet,
    parse_reading_packet,
    parse_stream_frame,
)
from .transport import (
    BrymenbleClient,
    COMMAND_CHAR_UUID,
    DEFAULT_PASSWORD,
    NOTIFY_CHAR_UUID,
    CommandError,
)
from .scanner import (
    DiscoveredMeter,
    find_first_meter,
    find_meters,
    is_brymenble_advertisement,
)

__version__ = "0.5.1"

__all__ = [
    "commands",
    "console",
    "constants",
    "crc",
    "formatter",
    "parsers",
    "scanner",
    "find_first_meter",
    "find_meters",
    "is_brymenble_advertisement",
    "DiscoveredMeter",
    "build_command_packet",
    "build_rtc_time_packet",
    "build_verify_password_packet",
    "calculate_crc",
    "verify_crc",
    "format_reading",
    "InfoPacket",
    "ReadingPacket",
    "RtcTime",
    "StreamFrame",
    "CommandResponse",
    "parse_info_packet",
    "parse_reading_packet",
    "parse_stream_frame",
    "parse_command_response",
    "BrymenbleClient",
    "CommandError",
    "COMMAND_CHAR_UUID",
    "DEFAULT_PASSWORD",
    "NOTIFY_CHAR_UUID",
]
