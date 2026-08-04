"""
Offline smoke test for the packet handling pipeline.

Builds a synthetic 152-byte stream frame (per the BM78xBT spec) and runs it
through the same code path that main.py uses (parsers -> formatter -> display),
so the whole pipeline can be verified WITHOUT the meter/BLE.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\smoke_test.py
"""
import contextlib
import io
import os
import sys

# Allow running directly from anywhere in the repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import crc
import display
import formatter
import parsers

# --- Synthetic frame builders (mirror the spec) -----------------------------------

def build_info_packet() -> bytes:
    pkt = bytearray(24)
    pkt[0:2] = b'\xFF\x01'          # head bytes
    pkt[2] = 0x18                   # length (24)
    pkt[3] = 0x04                   # packet type: Device Information
    pkt[4] = 0x01                   # protocol version
    pkt[5] = 0x02                   # device category: Multimeter
    pkt[6:12] = bytes.fromhex('BBA0507893CB')  # MAC
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
    """Build a Device Reading packet (default: 123.45 V, DCV)."""
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


def split_frame(data: bytes):
    """Split a frame exactly like the production notification path does."""
    return parsers.parse_stream_frame(data)


# --- Checks ------------------------------------------------------------------------

def check(label: str, condition: bool):
    if not condition:
        raise AssertionError(f"FAILED: {label}")
    print(f"  ok - {label}")


def main():
    frame = build_frame()
    assert len(frame) == 152, "frame length mismatch"

    info, readings = split_frame(frame)

    # --- Info packet ---
    check("info parsed (not None)", info is not None)
    check("info crc ok", info['crc_ok'] is True)
    check("category == 0x02", info['device_category'] == 0x02)
    check("mac == 00:11:22:33:44:55", info['mac'] == bytes.fromhex('BBA0507893CB'))
    check("battery == normal (0x00)", info['battery_status'] == 0x00)
    check("reading_packet_count == 4", info['reading_packet_count'] == 4)

    # --- Reading packets ---
    r0 = readings[0]
    check("reading[0] parsed", r0 is not None)
    check("reading[0] crc ok", r0['crc_ok'] is True)
    check("reading[0] function == DCV", r0['function_name'] == "DCV")
    check("reading[0] unit == V", r0['unit'] == "V")
    check("reading[0] raw_value == 12345", r0['raw_value'] == 12345)
    check("reading[0] prefix == ''", r0['prefix'] == "")
    check("reading[0] rtc.year == 2026", r0['rtc']['year'] == 2026)
    check("reading[0] rtc.month == 8", r0['rtc']['month'] == 8)
    check("reading[0] rtc.date == 4", r0['rtc']['date'] == 4)
    check("reading[0] rtc.hour == 12", r0['rtc']['hour'] == 12)
    check("reading[0] rtc.minute == 34", r0['rtc']['minute'] == 34)
    check("reading[0] rtc.second == 56", r0['rtc']['second'] == 56)
    check("reading[0] rtc.millisecond == 789", r0['rtc']['millisecond'] == 789)
    check("reading[1..3] are None (empty packets)", readings[1] is None and readings[2] is None and readings[3] is None)

    # --- Formatter ---
    check("format_reading == '123.45 V'", formatter.format_reading(r0) == "123.45 V")

    # --- Display (full print path) ---
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        display.print_frame(info, readings)
    out = buf.getvalue()
    check("display shows 'Multimeter'", "Multimeter" in out)
    check("display shows 'DCV'", "DCV" in out)
    check("display shows '123.45 V'", "123.45 V" in out)

    print("\nAll smoke checks passed.")


if __name__ == "__main__":
    main()
