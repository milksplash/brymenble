"""Tests for ``brymenble/console.py`` — the shared console output helpers.

Every consumer (``examples/live.py``, ``tools/connection_state.py``, the
display overlay, the TestController bridge) prints through these so their
console output is uniform; these lock down the format.
"""
import re

from brymenble import console
from brymenble.parsers import ReadingPacket


def test_ts_format():
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}", console.ts()
    )


def test_status_timestamped(capsys):
    console.status("hello")
    out = capsys.readouterr().out
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} CONSOLE hello\n", out
    )


def test_reading_line():
    assert console.reading_line(ReadingPacket.example()) == "DCV 607.80 V"
    assert console.reading_line(
        ReadingPacket.example(is_overload=True)) == "DCV OL"
    assert console.reading_line(
        ReadingPacket.example(is_ascii=True, ascii_text="Auto")) == "DCV Auto"
    assert console.reading_line(None) == "?"


def test_retry_callback(capsys):
    console.retry(2, 5, RuntimeError("boom"))
    assert "retry 2/5: boom" in capsys.readouterr().out


def test_retry_infinite(capsys):
    console.retry(1, None, RuntimeError("boom"))
    assert "retry 1: boom" in capsys.readouterr().out


def test_lost_reasons(capsys):
    console.lost()
    assert "meter powered off; reconnecting" in capsys.readouterr().out
    console.lost("pause_cap")
    assert "forcing reconnect" in capsys.readouterr().out


def test_scanning_helpers(capsys):
    console.scanning()
    console.scanning_retry(3)
    console.using("00:11:22:33:44:55", "METER")
    out = capsys.readouterr().out
    assert "scanning for a BM78xBT meter" in out
    assert "attempt 3" in out
    assert "using METER at 00:11:22:33:44:55" in out


def test_connecting_connected_disconnected(capsys):
    console.connecting("00:11:22:33:44:55")
    console.connected("00:11:22:33:44:55", detail="subscribed; listening")
    console.disconnected()
    out = capsys.readouterr().out
    assert "connecting to 00:11:22:33:44:55..." in out
    assert "connected to 00:11:22:33:44:55 — subscribed; listening" in out
    assert "disconnected" in out


def test_found(capsys):
    console.found("00:11:22:33:44:55", "BM78xBT", rssi=-42)
    console.found("00:11:22:33:44:55")
    out = capsys.readouterr().out
    assert "found BM78xBT at 00:11:22:33:44:55, rssi=-42" in out
    assert "found BM78xBT at 00:11:22:33:44:55" in out


def test_state_line(capsys):
    console.state("STREAMING", "link=up last=0.2s")
    out = capsys.readouterr().out
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} CONSOLE STREAMING +link=up last=0.2s\n",
        out,
    )
