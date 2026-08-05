# Lookup tables and enumerations for the BM78xBT protocol

# --- Packet framing / layout constants ----------------------------------------

# Fixed packet sizes (bytes)
INFO_PACKET_LENGTH = 24
READING_PACKET_LENGTH = 32
STREAM_FRAME_LENGTH = 152          # 1 info packet + 4 reading packets
READINGS_PER_FRAME = 4

# Byte [0] / [1]: header (HeadByte0 / HeadByte1)
HEAD_BYTE0 = 0xFF
HEAD_BYTE1_INFO = 0x01
HEAD_BYTE1_READING = 0x02

# Byte [2]: packet length field (always equals INFO/READING_PACKET_LENGTH)
# Byte [3]: packet type
INFO_PACKET_TYPE = 0x04            # Device Information
READING_PACKET_TYPE = 0x05         # Device Reading
# Byte [4]: protocol version
PROTOCOL_VERSION = 0x01

# Byte [30] / [31]: trailer (EndByte0 / EndByte1)
END_BYTE0 = 0xFF
END_BYTE1 = 0x03

# CRC-16 field: computed over bytes [start:end], stored little-endian at [end:end+2]
INFO_CRC_START = 2
INFO_CRC_END = 20
READING_CRC_START = 2
READING_CRC_END = 28

# --- Command packet framing (32 bytes) -----------------------------------------
COMMAND_PACKET_LENGTH = 32
COMMAND_HEAD_BYTE0 = 0xFF             # Byte [0]
COMMAND_HEAD_BYTE1 = 0x01             # Byte [1] (SOH)
COMMAND_PACKET_LEN_BYTE = 0x20        # Byte [2] (32)
COMMAND_PACKET_TYPE = 0x01            # Byte [3]: Command (0x02 = Response)
# Byte [4] protocol version: reuses PROTOCOL_VERSION
PASSWORD_ID = 0x01                    # Byte [13]: password identification
COMMAND_END_BYTE0 = 0xFF              # Byte [30]
COMMAND_END_BYTE1 = 0x03              # Byte [31] (ETX)
COMMAND_CRC_START = 2
COMMAND_CRC_END = 28

# Command IDs (2 bytes, little-endian on the wire)
CMD_VERIFY_PASSWORD = bytes([0x51, 0x01])   # 0x0151 (legacy bytes form)

# Full command table (numeric form; send_command / builders accept either)
CMD_GET_FIRMWARE_VERSION = 0x0004
CMD_RTC_TIME_CALIBRATION = 0x0010
CMD_GET_MODEL_SERIES_ID = 0x0116
CMD_SET_CONNECTION_PASSWORD = 0x0140
CMD_GET_CONNECTION_PASSWORD = 0x0141
CMD_SET_DEVICE_NAME = 0x0142
CMD_GET_DEVICE_NAME = 0x0143
CMD_VERIFY_CONNECTION_PASSWORD = 0x0151

# Command/response packet framing
COMMAND_RESPONSE_TYPE = 0x02            # Byte [3]: Response (0x01 = Command)
CMD_FAILURE = 0x8001                    # response Command ID signalling failure

# Error codes carried in 0x8001 failure responses (Arg[3:2], little-endian)
ERROR_CODES = {
    0: "Checksum error",
    1: "Invalid channel ID",
    2: "Out of setting range",
    3: "Invalid password",
    4: "Invalid password",
    5: "Invalid arguments",
    6: "Insufficient permissions",
}

# Device Category IDs
CATEGORY_MULTIMETER = 0x02
CATEGORY_CLAMP_METER = 0x03

# Battery Status
BATTERY_NORMAL = 0x00
BATTERY_LOW = 0x02

# Value -> human-readable name lookups
CATEGORY_NAMES = {
    CATEGORY_MULTIMETER: "Multimeter",
    CATEGORY_CLAMP_METER: "Clamp-on",
}

BATTERY_NAMES = {
    BATTERY_NORMAL: "Normal",
    BATTERY_LOW: "Low",
}

# Function IDs mapping (Main Function ID, Sub-Function ID -> description)
FUNCTION_NAMES = {
    (0x02, 0x00): "LoZ-ACV",
    (0x02, 0x01): "LoZ-DCV",
    (0x02, 0x03): "AUTO",
    (0x03, 0x00): "ACV",
    (0x03, 0x01): "DCV",
    (0x03, 0x02): "DC+ACV",
    (0x17, 0x00): "Hz of VFD-ACV",
    (0x17, 0x01): "VFD-ACV",
    (0x04, 0x00): "ACmV",
    (0x04, 0x01): "DCmV",
    (0x04, 0x02): "DC+ACmV",
    (0x05, 0x00): "ACµA",
    (0x05, 0x01): "DCµA",
    (0x05, 0x02): "DC+ACµA",
    (0x06, 0x00): "ACmA",
    (0x06, 0x01): "DCmA",
    (0x06, 0x02): "DC+ACmA",
    (0x06, 0x08): "%4~20mA",
    (0x07, 0x00): "ACA",
    (0x07, 0x01): "DCA",
    (0x07, 0x02): "DC+ACA",
    (0x0C, 0x00): "T1",
    (0x0C, 0x01): "T2",
    (0x0C, 0x02): "T1-T2",
    (0x0D, 0x00): "Resistance",
    (0x0E, 0x00): "Capacitance",
    (0x0F, 0x00): "Continuity",
    (0x10, 0x00): "Diode",
    (0x11, 0x00): "nS Conductance",
    (0x12, 0x00): "Duty Cycle (%)",
    (0x13, 0x00): "Logic-Hz",
    (0x22, 0x00): "EF-Lo",
    (0x22, 0x01): "EF-Hi",
    (0x23, 0x00): "Hz of Line Signal",
}

# Unit codes (Byte 26) -> SI unit string
UNIT_CODES = {
    0x02: "V",
    0x03: "A",
    0x04: "Ω",
    0x05: "S",
    0x06: "F",
    0x08: "Hz",
    0x0A: "%",
    0x14: "°C",
    0x15: "°F",
    0x4F: "% 4~20mA",
}

# Metrics Prefixes (Byte 25) -> symbol
PREFIX_MAP = {
    -9: "n",
    -6: "µ",
    -3: "m",
    0: "",
    3: "k",
    6: "M",
    9: "G",
}

# ASCII reading mappings (when Status Flag 0 Bit 2 = 1)
ASCII_READING_MAP = {
    0x000001: "Auto",
    0x000002: "InEr",
    0x000003: "-",
    0x000004: "--",
    0x000005: "---",
    0x000006: "----",
    0x000007: "-----",
    0x00000A: "EF-H",
    0x00000B: "EF-L",
}

# Status Flag 0 bit definitions (Byte 14)
STATUS0_CREST = 0x80
STATUS0_REL   = 0x40
STATUS0_HOLD  = 0x20
STATUS0_AUTO_RANGE = 0x10
STATUS0_AUTO_HOLD  = 0x08
STATUS0_ASCII_READING = 0x04

# Status Flag 1 bit definitions (Byte 15)
STATUS1_SIGN = 0x40
STATUS1_OL   = 0x20
STATUS1_RECORD = 0x10
STATUS1_MAX  = 0x08
STATUS1_MIN  = 0x04
STATUS1_AVG  = 0x02

# Status Flag 2 (Byte 16) is "don't care"