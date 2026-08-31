"""Shared console output for every brymenble consumer.

All streaming consumers — ``examples/live.py``, ``tools/connection_state.py``,
the display overlay, the TestController bridge — print the same timestamped
status lines, lifecycle events and reading format via this module, so the
console looks uniform no matter which tool is running.

Reading lines use the SDK's protocol-faithful formatter (overload -> ``OL``).
Consumers that add their own display accommodations at the UI layer (e.g. the
overlay/bridge showing ``----`` for a temperature overload) still override
there; the shared format itself stays protocol-faithful.
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional, TextIO

from .formatter import format_reading
from .parsers import ReadingPacket


def ts() -> str:
    """``YYYY-MM-DD HH:MM:SS,mmm`` prefix used by every status line.

    Matches logging's default ``asctime`` format so console lines line up
    with ``logging`` output (e.g. ``2026-08-31 21:46:49,330``).
    """
    now = datetime.now()
    return f"{now:%Y-%m-%d %H:%M:%S},{now.microsecond // 1000:03d}"


def status(message: str, *, stream: Optional[TextIO] = None) -> None:
    """Print a timestamped event line: ``YYYY-MM-DD HH:MM:SS,mmm CONSOLE message``."""
    print(f"{ts()} CONSOLE {message}", file=stream, flush=True)


def reading_line(reading: Optional[ReadingPacket]) -> str:
    """One-line display of a reading: ``DCV 607.80 V`` / ``Resistance OL``.

    Mirrors the meter LCD: ``<function> <value>``. Overload/ASCII states show
    as ``<function> OL`` / ``<function> <text>``.
    """
    if reading is None:
        return "?"
    if reading.is_overload:
        return f"{reading.function_name} OL"
    if reading.is_ascii:
        return f"{reading.function_name} {reading.ascii_text or '?'}"
    return f"{reading.function_name} {format_reading(reading)}"


# --- lifecycle events (drop-in SDK callbacks / wrappers) -----------------

def retry(attempt: int, max_retries: Optional[int], error: Exception) -> None:
    """SDK ``on_retry`` callback: ``... CONSOLE retry N[/M]: <error>``."""
    label = f"retry {attempt}" if max_retries is None else f"retry {attempt}/{max_retries}"
    status(f"{label}: {error}")


def paused(seconds: float = 1.0) -> None:
    """Link-up silence = pause (e.g. function switch). Deliberately silent:
    the pause is a lifecycle event (``on_pause``) that consumers act on — e.g.
    the overlay blanks its display — not a status line. Kept so
    ``on_pause=console.paused`` remains a valid hook."""


def lost(reason: str = "link_down") -> None:
    """SDK ``on_lost`` callback: link-down (power off) or pause_cap."""
    if reason == "pause_cap":
        status("link up but silent too long — forcing reconnect")
    else:
        status("BLE link lost — meter powered off; reconnecting")


def reconnected() -> None:
    """SDK ``on_reconnected`` callback."""
    status("reconnected and subscribed")


def scanning() -> None:
    status("scanning for a BM78xBT meter...")


def scanning_retry(attempt: int) -> None:
    status(f"no BM78xBT meter in range yet (attempt {attempt}) — retrying...")


def using(mac: str, name: Optional[str] = None) -> None:
    status(f"using {name or 'BM78xBT'} at {mac}")


def connecting(mac: str) -> None:
    """``... CONSOLE connecting to <mac>...``"""
    status(f"connecting to {mac}...")


def connected(mac: str, *, detail: Optional[str] = None) -> None:
    """``... CONSOLE connected to <mac>[ — <detail>]``"""
    suffix = f" — {detail}" if detail else ""
    status(f"connected to {mac}{suffix}")


def disconnected() -> None:
    """``... CONSOLE disconnected``"""
    status("disconnected")


def found(mac: str, name: Optional[str] = None, rssi: Optional[float] = None) -> None:
    """``... CONSOLE found <name> at <mac>[, rssi=..]`` — a meter from a scan."""
    label = name or "BM78xBT"
    rssi_txt = f", rssi={rssi}" if rssi is not None else ""
    status(f"found {label} at {mac}{rssi_txt}")


def state(name: str, detail: str, *, stream: Optional[TextIO] = None) -> None:
    """A link/data state-report line: ``... CONSOLE <name>  <detail>`` with the
    state name padded to a 20-char column (used by the connection-state tools)."""
    print(f"{ts()} CONSOLE {name:<20} {detail}", file=stream, flush=True)
