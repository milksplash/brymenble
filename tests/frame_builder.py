"""
Builders for synthetic BM78xBT packets, mirroring the protocol spec.

These are deliberately independent of the parser implementation so the tests
validate the real wire format rather than echoing the parser's own constants.
"""
from brymen import crc


def build_info_packet() -> bytes:
    """24-byte Device Information packet (Multimeter, MAC 00:11:22:33:44:55)."""
    pkt = bytearray(24)
    pkt[0:2] = b'\xFF\x01'          # head bytes
    pkt[2] = 0x18                   # length (24)
    pkt[3] = 0x04                   # packet type: Device Information
    pkt[4] = 0x01                   # protocol version
    pkt[5] = 0x02                   # device category: Multimeter
    # The real meter sends the MAC byte-reversed on the wire (bytes [6:12]
    # = 55:44:33:22:11:00 for display-order 00:11:22:33:44:55).
    pkt[6:12] = bytes.fromhex('CB937850A0BB')
    pkt[12] = 0x00                  # battery: Normal
    pkt[13] = 0x00                  # power source
    pkt[16] = 0x04                  # reading packet count
    pkt[19] = 0x01                  # device reading pk no.
    pkt[20:22] = crc.calculate_crc(pkt[2:20]).to_bytes(2, 'little')
    pkt[22:24] = b'\xFF\x03'        # end bytes
    return bytes(pkt)


def build_reading_packet(main_id=0x03, sub_id=0x01, raw_value=12345,
                         decimal_pos=3, prefix=0x00, unit=0x02,
                         display_digits=5) -> bytes:
    """32-byte Device Reading packet (default: 123.45 V, DCV)."""
    pkt = bytearray(32)
    pkt[0:2] = b'\xFF\x02'          # head bytes
    pkt[2] = 0x20                   # length (32)
    pkt[3] = 0x05                   # packet type: Device Reading
    pkt[4:7] = b'\x01\x00\x00'      # logging data set id = 0x000001 (little-endian)
    pkt[7] = 0x01                   # device reading pk id
    # RTC bytes [8..13] = 2026-08-04 12:34:56.789 (see spec bit layout)
    pkt[8:14] = bytes([0x15, 0xE3, 0x62, 0x04, 0x04, 0x35])
    pkt[14:17] = b'\x00\x00\x00'    # status flags
    pkt[17] = 0x01                  # device type: Meter
    pkt[18] = main_id               # main-function id
    pkt[19] = 0x00                  # reserved
    pkt[20] = sub_id                # sub-function id
    pkt[21:24] = raw_value.to_bytes(3, 'little', signed=True)  # 24-bit signed LE
    pkt[24] = decimal_pos
    pkt[25] = prefix
    pkt[26] = unit
    pkt[27] = display_digits
    pkt[28:30] = crc.calculate_crc(pkt[2:28]).to_bytes(2, 'little')
    pkt[30:32] = b'\xFF\x03'        # end bytes
    return bytes(pkt)


def build_frame() -> bytes:
    """152-byte stream: 1 info packet + 1 real reading + 3 empty readings."""
    frame = bytearray(152)
    frame[:24] = build_info_packet()
    frame[24:56] = build_reading_packet()
    # bytes 56..152 stay 0x00 (empty reading packets -> parser returns None)
    return bytes(frame)
