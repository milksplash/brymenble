"""Shared boilerplate for the example apps.

``examples/live.py`` and ``examples/debug_stream.py`` used to each carry ~60
identical lines of scan / connect / arg-parse / entry-point boilerplate. That
is now collected here; each example keeps only its per-app ``run_auto`` loop
and the handful of app-specific console hooks.
"""
import asyncio
import sys
from typing import Callable, Optional

from bleak import BleakError

from brymenble import (
    DEFAULT_PASSWORD, BrymenbleClient, CommandError, console, find_first_meter,
)

# Connection / reconnect policy.
SCAN_TIMEOUT = 5        # seconds to scan for a meter when no MAC is given
CONNECT_TIMEOUT = 5     # seconds to wait for a single connect attempt
RETRY_INTERVAL = 5      # seconds between reconnect attempts
MAX_RETRIES = 3         # max reconnect attempts before giving up
LINK_DOWN_GRACE = 2     # extra seconds to confirm a link drop before reconnecting


async def connect_client(mac: str, password: str) -> BrymenbleClient:
    """Create a client and connect it, applying the retry policy."""
    client = BrymenbleClient(
        mac, password, connect_timeout=CONNECT_TIMEOUT,
        sync_rtc_on_connect=True,
    )
    await client.ensure_connected(
        retries=MAX_RETRIES, retry_interval=RETRY_INTERVAL, on_retry=console.retry,
    )
    return client


def read_stream(client: BrymenbleClient):
    """Return ``client.read_stream()`` configured with the shared retry policy.

    ``BrymenbleClient.read_stream()`` owns the pause-vs-power-off decision: a
    data gap with the BLE link up is a function-switch pause (waited out, not
    reconnected); a link drop is confirmed with a grace window, then
    reconnected with the bounded retry policy above.
    """
    return client.read_stream(
        link_down_grace=LINK_DOWN_GRACE,
        retries=MAX_RETRIES,
        retry_interval=RETRY_INTERVAL,
        on_retry=console.retry,
        on_lost=console.lost,
        on_reconnected=console.reconnected,
    )


async def scan_for_meter(
    timeout: float = SCAN_TIMEOUT,
    *,
    announce: Callable[[object], None] = console.using,
) -> str:
    """Scan for the first BM78xBT meter and return its MAC address.

    ``announce`` is called with the found meter so each app can log it its own
    way (``console.using`` vs ``console.found`` with RSSI).
    """
    console.scanning()
    meter = await find_first_meter(timeout=timeout, retry_interval=0)
    if meter is None:
        raise ConnectionError(
            "No BM78xBT meters found — power the meter on and retry, or "
            "pass its MAC address explicitly."
        )
    announce(meter)
    return meter.address


async def _main(run_auto, mac: Optional[str], password: str, *,
               connected_detail: str, announce_found: Callable[[object], None],
               on_mac_provided: Optional[Callable[[str], None]] = None):
    if mac is None:
        mac = await scan_for_meter(announce=announce_found)
    elif on_mac_provided is not None:
        on_mac_provided(mac)
    console.connecting(mac)
    client = await connect_client(mac, password)
    try:
        console.connected(mac, detail=connected_detail)
        await run_auto(client)
    finally:
        await client.close()
    console.disconnected()


def parse_args(argv):
    mac = None  # None -> auto-scan for a meter
    password = DEFAULT_PASSWORD
    for arg in argv:
        if ":" in arg:  # likely a MAC
            mac = arg
        elif arg.isdigit() and len(arg) == 4:
            password = arg
    return mac, password


def run(run_auto, *, connected_detail: str,
        announce_found: Callable[[object], None] = console.using,
        on_mac_provided: Optional[Callable[[str], None]] = None) -> None:
    """Parse argv and drive ``main`` with the standard error handling."""
    mac, password = parse_args(sys.argv[1:])
    try:
        sys.exit(asyncio.run(_main(
            run_auto, mac, password, connected_detail=connected_detail,
            announce_found=announce_found, on_mac_provided=on_mac_provided,
        )))
    except KeyboardInterrupt:
        print("\nProgram terminated.")
        sys.exit(130)
    except (ConnectionError, CommandError, BleakError) as exc:
        # No traceback for expected failures (reconnect exhausted, bad
        # password, ...) — just a clean one-line message.
        print(f"Error: {exc}")
        sys.exit(1)
