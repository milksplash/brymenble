"""
Tests for the BM78xBT packet handling pipeline: parsers -> formatter -> display.

Run from the project root:
    .venv\\Scripts\\python.exe -m pytest
"""
import contextlib
import io

from brymen import constants, crc, formatter, parsers

import display
from tests.frame_builder import build_frame, build_info_packet, build_reading_packet

# Transport-layer unit tests (connect/auth/subscribe, reconnect, wait_frame,
# no-data watchdog, GATT timeouts, worker-thread notifications) live in
# tests/test_transport.py with a faked BleakClient.


def _frame():
    """Parse the standard 152-byte test frame, asserting it is valid."""
    frame = parsers.parse_stream_frame(build_frame())
    assert frame is not None
    return frame


# --- Info packet ---------------------------------------------------------------

def test_info_packet_parsed():
    assert _frame().info is not None


def test_info_packet_fields():
    info = _frame().info
    assert info.crc_ok is True
    assert info.device_category == 0x02
    assert info.mac == bytes.fromhex('001122334455')
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
    r0 = _frame().readings[0]
    assert r0 is not None
    assert r0.crc_ok is True
    assert r0.function_name == "DCV"
    assert r0.unit == "V"
    assert r0.mantissa == 12345
    assert r0.prefix == ""
    assert r0.display_digit_count == 5


def test_reading_packet_rtc():
    rtc = _frame().readings[0].rtc
    assert rtc.year == 2026
    assert rtc.month == 8
    assert rtc.date == 4
    assert rtc.hour == 12
    assert rtc.minute == 34
    assert rtc.second == 56
    assert rtc.millisecond == 789


def test_reading_packet_rtc_hour_layout():
    # Regression: hour 20 (0b10100) must decode as 20, not 5 (0b00101).
    # The meter packs hour as byte10[7:6] (LOW 2 bits) + byte11[2:0] (HIGH 3).
    pkt = bytearray(32)
    pkt[0:2] = b'\xFF\x02'
    pkt[2] = 0x20
    pkt[3] = 0x05
    pkt[10] = 0x00           # minute 0, byte10[7:6] = 0 (low 2 bits of 20)
    pkt[11] = 0b101          # byte11[2:0] = 5 (high 3 bits of 20)
    rtc = parsers.parse_reading_packet(bytes(pkt)).rtc
    assert rtc.hour == 20


def test_empty_reading_packets_return_none():
    readings = _frame().readings
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


def test_reading_packet_raw_fields():
    # Logging Data Set ID [4..6] (little-endian), Reading PK ID [7], Device
    # Type [17] (0 = Sensor, 1 = Meter).
    r0 = _frame().readings[0]
    assert r0 is not None
    assert r0.logging_data_set_id == 0x000001
    assert r0.device_reading_pk_id == 0x01
    assert r0.device_type == 0x01


def test_reading_packet_status_flags_decoded():
    # All meaningful Status Flag 0/1 bits decode to named booleans.
    status0 = (constants.STATUS0_CREST | constants.STATUS0_REL
               | constants.STATUS0_HOLD | constants.STATUS0_AUTO_RANGE
               | constants.STATUS0_AUTO_HOLD | constants.STATUS0_ASCII_READING)
    status1 = (constants.STATUS1_SIGN | constants.STATUS1_OL
               | constants.STATUS1_RECORD | constants.STATUS1_MAX
               | constants.STATUS1_MIN | constants.STATUS1_AVG)
    r = parsers.parse_reading_packet(
        _reading_with_status(status0=status0, status1=status1))
    assert r is not None
    assert (r.is_crest, r.is_relative, r.is_held, r.is_auto_range,
            r.is_auto_hold, r.is_ascii) == (True, True, True, True, True, True)
    assert (r.is_negative, r.is_overload, r.is_recording, r.is_max,
            r.is_min, r.is_avg) == (True, True, True, True, True, True)


def test_reading_packet_status_flags_clear():
    r = parsers.parse_reading_packet(_reading_with_status(status0=0, status1=0))
    assert r is not None
    assert not any((r.is_crest, r.is_relative, r.is_held, r.is_auto_range,
                    r.is_auto_hold, r.is_ascii, r.is_negative, r.is_overload,
                    r.is_recording, r.is_max, r.is_min, r.is_avg))


# --- Canonical value surface (mantissa / signed_value / value / decimals) -----

def test_reading_value_surface():
    r0 = _frame().readings[0]
    assert r0.decimals == 2            # 5 display digits - decimal_pos 3
    assert r0.signed_value == 12345
    assert r0.value == 123.45
    assert r0.mantissa == 12345


def test_reading_value_decimal_pos_zero():
    # decimal_pos 0 = no decimal point -> decimals 0, value is the mantissa.
    pkt = bytearray(build_reading_packet(decimal_pos=0))
    r = parsers.parse_reading_packet(bytes(pkt))
    assert r is not None
    assert r.decimals == 0
    assert r.value == 12345.0


def test_reading_value_sign_flag_applies_to_magnitude():
    # SIGN flag + positive wire bytes -> negative signed value / formatter.
    pkt = _reading_with_status(status0=0, status1=constants.STATUS1_SIGN)
    r = parsers.parse_reading_packet(pkt)
    assert r is not None
    assert r.is_negative
    assert r.mantissa == 12345         # magnitude, never sign-bearing
    assert r.signed_value == -12345
    assert r.value == -123.45
    assert formatter.format_reading(r) == "-123.45 V"


def test_reading_wire_negative_becomes_magnitude():
    # A negative 24-bit wire value decodes to a magnitude + the SIGN flag —
    # the two never combine (regression for the old abs()+flag footgun).
    pkt = bytearray(build_reading_packet(raw_value=-12345))
    pkt[15] = constants.STATUS1_SIGN
    pkt[28:30] = crc.calculate_crc(bytes(pkt[2:28])).to_bytes(2, 'little')
    r = parsers.parse_reading_packet(bytes(pkt))
    assert r is not None
    assert r.is_negative
    assert r.mantissa == 12345
    assert r.signed_value == -12345


def test_reading_mantissa_always_magnitude():
    # Hand-built packet with a negative mantissa is normalized to a magnitude.
    r = parsers.ReadingPacket(
        function_name="DCV", unit="V", mantissa=-61, decimal_pos=3,
        prefix="", display_digit_count=4, logging_data_set_id=1,
        device_reading_pk_id=1, device_type=1, status0=0, status1=0,
        rtc=parsers.RtcTime(2026, 1, 1, 0, 0, 0, 0),
        is_crest=False, is_relative=False, is_held=False,
        is_auto_range=False, is_auto_hold=False, is_ascii=False,
        is_negative=True, is_overload=False, is_recording=False,
        is_max=False, is_min=False, is_avg=False,
        ascii_text=None, crc_ok=True, raw=b"",
    )
    assert r.mantissa == 61
    assert r.signed_value == -61
    assert r.value == -6.1      # digits 4 - decimal_pos 3 = 1 decimal place


def test_reading_value_overload_ascii_are_none():
    ol = parsers.parse_reading_packet(
        _reading_with_status(status0=0, status1=constants.STATUS1_OL))
    assert ol is not None and ol.value is None
    ascii_r = parsers.parse_reading_packet(
        _reading_with_status(status0=constants.STATUS0_ASCII_READING,
                             status1=0, raw_value=0x000001))
    assert ascii_r is not None and ascii_r.value is None


def test_reading_to_dict():
    r0 = _frame().readings[0]
    d = r0.to_dict()
    assert d["mantissa"] == 12345
    assert d["signed_value"] == 12345
    assert d["value"] == 123.45
    assert d["decimals"] == 2
    assert d["unit"] == "V"
    assert d["rtc"]["year"] == 2026
    assert d["raw_hex"] == r0.raw.hex()


def test_stream_frame_to_dict():
    frame = _frame()
    d = frame.to_dict()
    assert d["info"]["mac"] == "00:11:22:33:44:55"
    assert d["readings"][0]["value"] == 123.45
    assert d["readings"][1] is None


# --- Stream framing ------------------------------------------------------------

def test_frame_wrong_length_returns_none():
    assert parsers.parse_stream_frame(b'\x00' * 100) is None


# --- Formatter -----------------------------------------------------------------

def _reading_with_status(status0: int, status1: int, raw_value: int = 12345) -> bytes:
    """Reading-packet bytes with the given status flags and CRC fixed."""
    pkt = bytearray(build_reading_packet(raw_value=raw_value))
    pkt[14] = status0
    pkt[15] = status1
    pkt[28:30] = crc.calculate_crc(bytes(pkt[2:28])).to_bytes(2, 'little')
    return bytes(pkt)


def test_format_reading():
    assert formatter.format_reading(_frame().readings[0]) == "123.45 V"


def test_format_reading_none():
    assert formatter.format_reading(None) == "Invalid packet"


def test_format_reading_overload():
    # End-to-end: OL status bit -> parse -> format as "OL".
    pkt = _reading_with_status(status0=0, status1=constants.STATUS1_OL)
    r = parsers.parse_reading_packet(pkt)
    assert r is not None and r.is_overload
    assert formatter.format_reading(r) == "OL"


def test_format_reading_ascii():
    # End-to-end: ASCII status bit + raw_value in ASCII_READING_MAP.
    pkt = _reading_with_status(
        status0=constants.STATUS0_ASCII_READING, status1=0, raw_value=0x000001)
    r = parsers.parse_reading_packet(pkt)
    assert r is not None and r.is_ascii
    assert r.ascii_text == "Auto"
    assert formatter.format_reading(r) == "Auto"


def test_format_reading_ascii_unknown():
    # raw_value not in the ASCII map -> hex fallback string.
    pkt = _reading_with_status(
        status0=constants.STATUS0_ASCII_READING, status1=0, raw_value=0x000010)
    r = parsers.parse_reading_packet(pkt)
    assert r is not None and r.is_ascii
    assert formatter.format_reading(r) == "0x000010"


def test_format_reading_ascii_no_text():
    # Constructed packet with is_ascii but no mapped text -> "???".
    r = parsers.ReadingPacket(
        function_name="DCV", unit="V", mantissa=1, decimal_pos=3, prefix="",
        display_digit_count=5, logging_data_set_id=1, device_reading_pk_id=1,
        device_type=1, status0=constants.STATUS0_ASCII_READING, status1=0,
        rtc=parsers.RtcTime(2026, 1, 1, 0, 0, 0, 0),
        is_crest=False, is_relative=False, is_held=False,
        is_auto_range=False, is_auto_hold=False, is_ascii=True,
        is_negative=False, is_overload=False, is_recording=False,
        is_max=False, is_min=False, is_avg=False,
        ascii_text=None, crc_ok=True, raw=b"",
    )
    assert formatter.format_reading(r) == "???"


# --- Display -------------------------------------------------------------------

def test_display_frame():
    frame = _frame()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        display.print_frame(frame.info, frame.readings)
    out = buf.getvalue()
    assert "Value: 123.45 V" in out
    assert "Function: DCV" in out
    assert "Device Time:" in out


# --- CRC known-answer (verified against the protocol document) -----------------

def test_crc_info_packet():
    # Known answer for the synthetic 24-byte info packet (MAC 00:11:22:33:44:55).
    # 0xAED9 (bytes D9 AE) was the real meter's info CRC from the old,
    # locally-kept captures.json, before the MAC was scrubbed from the repo.
    assert crc.calculate_crc(build_info_packet()[2:20]) == 0x9E27


def test_crc_reading_packet():
    # 0x280D is the CRC of the synthetic reading packet with the corrected
    # RTC bytes (hour-layout fix changed bytes 10..11 vs the old 0xCDAA).
    assert crc.calculate_crc(build_reading_packet()[2:28]) == 0x280D
