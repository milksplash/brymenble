"""Debug/test script for the brymenble SDK — raw protocol stream dump.

Connects to a Brymen BM78xBT multimeter over BLE and prints every frame as it
arrives via ``display.py``: the full raw frame hex, the device-info packet
(raw hex + parsed fields), each reading packet (raw hex + parsed fields), and
rolling packet-timing statistics.

This is a *debugging* tool for inspecting what the meter actually sends — the
clean, console-friendly version of this app is ``examples/live.py`` (which
uses the shared ``brymenble.console`` output helpers instead).

Without a MAC, the debug stream scans for the first BM78xBT meter it finds.

Usage:
    python examples/debug_stream.py [MAC] [PASSWORD]

Examples:
    python examples/debug_stream.py               # scan, then connect to the first meter
    python examples/debug_stream.py 00:11:22:33:44:55 1234
"""
import display
from brymenble import BrymenbleClient, console

from _common import read_stream, run


async def run_auto(client: BrymenbleClient):
    """Print each raw frame as it arrives; reconnects are handled by the SDK.

    ``BrymenbleClient.read_stream()`` owns the pause-vs-power-off decision: a
    data gap with the BLE link up is a function-switch pause (waited out, not
    reconnected); a link drop is confirmed with a grace window, then
    reconnected with the bounded retry policy in ``_common``.
    """
    console.status("debug stream: printing raw frames as they arrive (Ctrl+C to quit)")

    async for frame in read_stream(client):
        display.print_frame(frame)


def _announce_found(meter) -> None:
    console.found(meter.address, meter.name, meter.rssi)


def main() -> None:
    run(
        run_auto,
        connected_detail="subscribed; listening for data",
        announce_found=_announce_found,
    )


if __name__ == "__main__":
    main()
