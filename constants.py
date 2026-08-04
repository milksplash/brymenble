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