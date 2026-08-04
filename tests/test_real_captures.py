"""
End-to-end tests against real frames captured from the meter.

The suite skips (with a message) until at least one capture exists. To collect
real frames, run:
    .venv\\Scripts\\python.exe tools\\capture.py [MAC]
which appends labeled frames to tests/fixtures/captures.json.
"""
import json
import os

import pytest

from brymen import formatter, parsers

FIXTURES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "captures.json"
)


def load_captures():
    if not os.path.exists(FIXTURES_FILE):
        return []
    with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


captures = load_captures()


def test_real_captures_available():
    if not captures:
        pytest.skip("No real captures yet - run: .venv\\Scripts\\python.exe tools\\capture.py")


@pytest.mark.parametrize("cap", captures)
def test_real_capture_parses_to_ground_truth(cap):
    frame = bytes.fromhex(cap["hex"])
    info, readings = parsers.parse_stream_frame(frame)

    assert info is not None, f"{cap['name']}: no info packet"
    assert info.crc_ok is True, f"{cap['name']}: info packet CRC failed"
    assert info.mac_str == "00:11:22:33:44:55", (
        f"{cap['name']}: unexpected MAC {info.mac_str}"
    )

    r0 = readings[0]
    assert r0 is not None, f"{cap['name']}: first reading packet missing"
    assert r0.crc_ok is True, f"{cap['name']}: reading packet CRC failed"

    parsed = formatter.format_reading(r0)
    assert parsed == cap["expected"], (
        f"{cap['name']}: parsed '{parsed}' != ground truth '{cap['expected']}'"
    )
