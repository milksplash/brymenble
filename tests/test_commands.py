"""Tests for BM78xBT command packet building and response parsing."""
from datetime import datetime

import pytest

from brymenble import commands, constants, crc, parsers

MAC = "00:11:22:33:44:55"


def test_packet_is_32_bytes():
    pkt = commands.build_verify_password_packet(MAC)
    assert len(pkt) == 32


def test_verify_password_packet_structure():
    pkt = commands.build_verify_password_packet(MAC, "1234")
    assert pkt[0:2] == b'\xFF\x01'                        # header
    assert pkt[2] == 0x20                                 # length (32)
    assert pkt[3] == 0x01                                 # packet type: Command
    assert pkt[4] == 0x01                                 # protocol version
    assert pkt[5:11] == bytes.fromhex('554433221100')     # MAC, reversed
    assert pkt[11:13] == constants.CMD_VERIFY_PASSWORD    # command ID
    assert pkt[13] == 0x01                                # password id
    assert pkt[14:18] == b'\x01\x02\x03\x04'              # password digits
    assert pkt[18:28] == b'\x00' * 10                     # padding
    assert pkt[30:32] == b'\xFF\x03'                      # footer


def test_verify_password_packet_crc():
    pkt = commands.build_verify_password_packet(MAC)
    assert crc.calculate_crc(pkt[2:28]) == int.from_bytes(pkt[28:30], 'little')


def test_verify_password_invalid():
    with pytest.raises(ValueError):
        commands.build_verify_password_packet(MAC, "12")     # too short
    with pytest.raises(ValueError):
        commands.build_verify_password_packet(MAC, "abcd")   # non-digit


def test_encode_password_args():
    # The shared digit->byte mapping used by both the command builder and the
    # transport layer's connection-password verify.
    assert commands.encode_password_args("1234") == b'\x01\x02\x03\x04'
    assert commands.encode_password_args("0000") == b'\x00\x00\x00\x00'


def test_command_packet_bad_mac():
    with pytest.raises(ValueError):
        commands.build_command_packet("00:11", constants.CMD_VERIFY_PASSWORD)


def test_command_packet_bad_command_id():
    with pytest.raises(ValueError):
        commands.build_command_packet(MAC, b'\x00')          # 1-byte command id


def test_command_packet_out_of_range_int_command_id():
    # An int command_id outside 0-0xFFFF must raise ValueError (not
    # OverflowError) to keep the exception contract consistent.
    with pytest.raises(ValueError):
        commands.build_command_packet(MAC, 0x10000)
    with pytest.raises(ValueError):
        commands.build_command_packet(MAC, -1)


def test_command_packet_oversized_args_rejected():
    # args longer than 14 bytes would silently violate the 32-byte framing
    # invariant; reject them with ValueError.
    with pytest.raises(ValueError):
        commands.build_command_packet(MAC, constants.CMD_RTC_TIME_CALIBRATION, b'\x00' * 15)
    with pytest.raises(ValueError):
        commands.build_command_packet(MAC, constants.CMD_RTC_TIME_CALIBRATION, b'\x00' * 20)


def test_command_packet_max_args_ok():
    # Exactly 14 bytes of args is the maximum allowed and must build fine.
    pkt = commands.build_command_packet(
        MAC, constants.CMD_RTC_TIME_CALIBRATION, b'\x01' * 14
    )
    assert len(pkt) == 32


def test_command_packet_accepts_int_command_id():
    pkt_int = commands.build_command_packet(MAC, constants.CMD_RTC_TIME_CALIBRATION)
    pkt_bytes = commands.build_command_packet(
        MAC, constants.CMD_RTC_TIME_CALIBRATION.to_bytes(2, 'little')
    )
    assert pkt_int == pkt_bytes
    assert pkt_int[11:13] == bytes.fromhex('1000')        # 0x0010 little-endian


def _as_response(pkt: bytes) -> bytes:
    """Turn a command packet into a response packet (type 0x02, CRC fixed)."""
    p = bytearray(pkt)
    p[3] = 0x02                                            # Response type
    p[28:30] = crc.calculate_crc(bytes(p[2:28])).to_bytes(2, 'little')
    return bytes(p)


def test_parse_command_response_success():
    args = bytes([30, 15, 12, 4, 2, 8, 26])               # sec..year-2000
    pkt = commands.build_command_packet(
        MAC, constants.CMD_RTC_TIME_CALIBRATION, args
    )
    resp = parsers.parse_command_response(_as_response(pkt))
    assert resp is not None
    assert resp.crc_ok is True
    assert resp.command_id == constants.CMD_RTC_TIME_CALIBRATION
    assert resp.args == args.ljust(14, b'\x00')
    assert resp.is_failure is False


def test_parse_command_response_failure():
    # 0x8001 frame: Arg[0:2] = failing command (0x0010), Arg[2:4] = error code 3
    args = (
        constants.CMD_RTC_TIME_CALIBRATION.to_bytes(2, 'little')
        + (3).to_bytes(2, 'little')
        + b'\x00' * 10
    )
    pkt = commands.build_command_packet(MAC, constants.CMD_FAILURE, args)
    resp = parsers.parse_command_response(_as_response(pkt))
    assert resp is not None
    assert resp.crc_ok is True
    assert resp.is_failure is True
    assert resp.command_id == constants.CMD_FAILURE
    assert resp.failed_command_id == constants.CMD_RTC_TIME_CALIBRATION
    assert resp.error_code == 3
    assert resp.error_message == "Invalid password"


def test_parse_command_response_invalid():
    assert parsers.parse_command_response(b'\x00' * 32) is None
    # a command packet (type 0x01) is not a response
    pkt = commands.build_command_packet(MAC, constants.CMD_RTC_TIME_CALIBRATION)
    assert parsers.parse_command_response(bytes(pkt)) is None


def test_rtc_time_args_encoding():
    # 2026-01-02 is a Friday: sec,min,hr,date,day-of-week(Mon=1),month,year-2000
    args = commands.encode_rtc_time_args(datetime(2026, 1, 2, 3, 4, 5))
    assert args[0:7] == bytes([5, 4, 3, 2, 5, 1, 26])
    assert len(args) == 14


def test_build_rtc_time_packet():
    pkt = commands.build_rtc_time_packet(MAC, datetime(2026, 1, 2, 3, 4, 5))
    assert len(pkt) == 32
    assert pkt[3] == 0x01                                      # Command type
    assert pkt[11:13] == constants.CMD_RTC_TIME_CALIBRATION.to_bytes(2, 'little')
    assert pkt[14:21] == bytes([5, 4, 3, 2, 5, 1, 26])
    assert crc.calculate_crc(pkt[2:28]) == int.from_bytes(pkt[28:30], 'little')
