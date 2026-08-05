"""brymenble — unofficial, open-source SDK for the Brymen BM78xBT BLE multimeter.

Public API:

- ``BrymenClient``: connect/authenticate/subscribe and stream parsed frames
- ``parsers``: ``InfoPacket`` / ``ReadingPacket`` / ``RtcTime`` and parse helpers
- ``commands``: command-packet builders
- ``formatter``: turn a parsed reading into a display string
- ``crc`` / ``constants``: protocol primitives

TODO: no discovery/scanning helper yet — add a scanner that finds BM78xBT
meters from their BLE advertising packets (device name / model series ID).
"""

from . import commands, constants, crc, formatter, parsers
from .commands import build_command_packet, build_verify_password_packet
from .crc import calculate_crc, verify_crc
from .formatter import format_reading
from .parsers import (
    CommandResponse,
    InfoPacket,
    ReadingPacket,
    RtcTime,
    parse_command_response,
    parse_info_packet,
    parse_reading_packet,
    parse_stream_frame,
)
from .transport import (
    BrymenClient,
    COMMAND_CHAR_UUID,
    DEFAULT_PASSWORD,
    NOTIFY_CHAR_UUID,
    CommandError,
)

__version__ = "0.1.0"

__all__ = [
    "commands",
    "constants",
    "crc",
    "formatter",
    "parsers",
    "build_command_packet",
    "build_verify_password_packet",
    "calculate_crc",
    "verify_crc",
    "format_reading",
    "InfoPacket",
    "ReadingPacket",
    "RtcTime",
    "CommandResponse",
    "parse_info_packet",
    "parse_reading_packet",
    "parse_stream_frame",
    "parse_command_response",
    "BrymenClient",
    "CommandError",
    "COMMAND_CHAR_UUID",
    "DEFAULT_PASSWORD",
    "NOTIFY_CHAR_UUID",
]
