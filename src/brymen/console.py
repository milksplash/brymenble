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
    """``[HH:MM:SS]`` prefix used by every status line."""
    return datetime.now().strftime("%H:%M:%S")


def status(message: str, *, stream: Optional[TextIO] = None) -> None:
    """Print a timestamped event line: ``[HH:MM:SS] message``."""
    print(f"[{ts()}] {message}", file=stream, flush=True)


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
    """SDK ``on_retry`` callback: ``[HH:MM:SS] retry N[/M]: <error>``."""
    label = f"retry {attempt}" if max_retries is None else f"retry {attempt}/{max_retries}"
    status(f"{label}: {error}")


def paused(seconds: float) -> None:
    """Link-up silence = pause (e.g. function switch). Wrap to bind seconds:
    ``on_pause=lambda: console.paused(NO_DATA_TIMEOUT)``."""
    status(f"no data for {seconds:.0f}s but BLE link still up — "
           "meter paused (e.g. function switch); waiting")


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
