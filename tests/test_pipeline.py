"""
Tests for the BM78xBT packet handling pipeline: parsers -> formatter -> display.

Run from the project root:
    .venv\\Scripts\\python.exe -m pytest
"""
import contextlib
import io

from brymen import crc, formatter, parsers

import display
from tests.frame_builder import build_frame, build_info_packet, build_reading_packet


# --- Info packet ---------------------------------------------------------------

def test_info_packet_parsed():
    info, _ = parsers.parse_stream_frame(build_frame())
    assert info is not None


def test_info_packet_fields():
    info, _ = parsers.parse_stream_frame(build_frame())
    assert info.crc_ok is True
    assert info.device_category == 0x02
    assert info.mac == bytes.fromhex('BBA0507893CB')
    assert info.battery_status == 0x00
    assert info.reading_packet_count == 4
    assert info.category_name == "Multimeter"
    assert info.battery_name == "Normal"
    assert info.mac_str == "00:11:22:33:44:55"


def test_info_packet_invalid_length_returns_none():
    assert parsers.parse_info_packet(b'\x00' * 23) is None


def test_info_packet_bad_header_returns_none():
    pkt = bytearray(build_info_packet())
    pkt[0] = 0x00  # corrupt head byte
    assert parsers.parse_info_packet(bytes(pkt)) is None


def test_info_packet_crc_failure_flagged():
    pkt = bytearray(build_info_packet())
    pkt[5] = 0x03  # change category without recomputing CRC
    parsed = parsers.parse_info_packet(bytes(pkt))
    assert parsed is not None
    assert parsed.crc_ok is False
    assert parsed.device_category == 0x03
    assert parsed.category_name == "Clamp-on"


# --- Reading packet ------------------------------------------------------------

def test_reading_packet_fields():
    _, readings = parsers.parse_stream_frame(build_frame())
    r0 = readings[0]
    assert r0 is not None
    assert r0.crc_ok is True
    assert r0.function_name == "DCV"
    assert r0.unit == "V"
    assert r0.raw_value == 12345
    assert r0.prefix == ""
    assert r0.display_digit_count == 5


def test_reading_packet_rtc():
    _, readings = parsers.parse_stream_frame(build_frame())
    rtc = readings[0].rtc
    assert rtc.year == 2026
    assert rtc.month == 8
    assert rtc.date == 4
    assert rtc.hour == 12
    assert rtc.minute == 34
    assert rtc.second == 56
    assert rtc.millisecond == 789


def test_empty_reading_packets_return_none():
    _, readings = parsers.parse_stream_frame(build_frame())
    assert readings[1] is None
    assert readings[2] is None
    assert readings[3] is None


def test_reading_packet_invalid_length_returns_none():
    assert parsers.parse_reading_packet(b'\x00' * 31) is None


def test_reading_packet_crc_failure_flagged():
    pkt = bytearray(build_reading_packet())
    pkt[18] = 0x07  # change main function id without recomputing CRC
    parsed = parsers.parse_reading_packet(bytes(pkt))
    assert parsed is not None
    assert parsed.crc_ok is False


# --- Stream framing ------------------------------------------------------------

def test_frame_wrong_length_returns_none_none():
    assert parsers.parse_stream_frame(b'\x00' * 100) == (None, None)


# --- Formatter -----------------------------------------------------------------

def test_format_reading():
    _, readings = parsers.parse_stream_frame(build_frame())
    assert formatter.format_reading(readings[0]) == "123.45 V"


def test_format_reading_none():
    assert formatter.format_reading(None) == "Invalid packet"


# --- Display -------------------------------------------------------------------

def test_display_frame():
    info, readings = parsers.parse_stream_frame(build_frame())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        display.print_frame(info, readings)
    out = buf.getvalue()
    assert "Multimeter" in out
    assert "DCV" in out
    assert "123.45 V" in out


# --- CRC known-answer (verified against the protocol document) -----------------

def test_crc_info_packet():
    # 0xAED9 matches the real meter's info CRC (bytes D9 AE) - see captures.json.
    assert crc.calculate_crc(build_info_packet()[2:20]) == 0xAED9


def test_crc_reading_packet():
    assert crc.calculate_crc(build_reading_packet()[2:28]) == 0xCDAA
