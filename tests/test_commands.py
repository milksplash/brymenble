"""Tests for BM78xBT command packet building."""
import pytest

from brymen import commands, constants, crc

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
    assert pkt[5:11] == bytes.fromhex('CB937850A0BB')     # MAC, reversed
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


def test_command_packet_bad_mac():
    with pytest.raises(ValueError):
        commands.build_command_packet("00:11", constants.CMD_VERIFY_PASSWORD)


def test_command_packet_bad_command_id():
    with pytest.raises(ValueError):
        commands.build_command_packet(MAC, b'\x00')          # 1-byte command id
