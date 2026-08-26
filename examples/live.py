"""Live-readings console app for the brymenble SDK.

Connects to a Brymen BM78xBT multimeter over BLE and streams its readings to
the console continuously as they arrive, using the shared ``brymenble.console``
output helpers (same format as the overlay and the TC bridge).

Without a MAC, the console scans for the first BM78xBT meter it finds.

For a raw protocol view (info packet / reading packet / full frame hex + packet
statistics), see ``examples/debug_stream.py``.

Usage:
    python examples/live.py [MAC] [PASSWORD]

Examples:
    python examples/live.py               # scan, then connect to the first meter
    python examples/live.py 00:11:22:33:44:55 1234
"""
"""Live-readings console app for the brymenble SDK.

Connects to a Brymen BM78xBT multimeter over BLE and streams its readings to
the console continuously as they arrive, using the shared ``brymenble.console``
output helpers (same format as the overlay and the TC bridge).

Without a MAC, the console scans for the first BM78xBT meter it finds.

For a raw protocol view (info packet / reading packet / full frame hex + packet
statistics), see ``examples/debug_stream.py``.

Usage:
    python examples/live.py [MAC] [PASSWORD]

Examples:
    python examples/live.py               # scan, then connect to the first meter
    python examples/live.py 00:11:22:33:44:55 1234
"""
from brymenble import BrymenbleClient, console

from _common import read_stream, run


async def run_auto(client: BrymenbleClient):
    """Print each reading as it arrives; reconnects are handled by the SDK.

    ``BrymenbleClient.read_stream()`` owns the pause-vs-power-off decision: a
    data gap with the BLE link up is a function-switch pause (waited out, not
    reconnected); a link drop is confirmed with a grace window, then
    reconnected with the bounded retry policy in ``_common``.
    """
    console.status("auto mode: readings appear as they arrive (Ctrl+C to quit)")

    async for frame in read_stream(client):
        for r in frame.readings or ():
            if r is not None:
                console.status(console.reading_line(r))


def _announce_found(meter) -> None:
    console.using(meter.address, meter.name)


def _announce_mac(mac: str) -> None:
    console.using(mac)


def main() -> None:
    run(
        run_auto,
        connected_detail="subscribed; listening",
        announce_found=_announce_found,
        on_mac_provided=_announce_mac,
    )


if __name__ == "__main__":
    main()
