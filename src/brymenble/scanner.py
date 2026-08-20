"""Discovery of BM78xBT meters via BLE advertising (protocol spec section 1).

A BM78xBT advertises a fixed manufacturer-data payload (company ID ``0x0131``
followed by ``b'BM'`` + model-series ``0x0B``) and may also advertise the
primary service UUID ``0003CDD0-...``. ``find_meters()`` scans for devices
matching either fingerprint so you don't need to know the MAC up front.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable, List, Optional

from bleak import BleakScanner
from bleak.backends.scanner import AdvertisementData, BLEDevice

# Primary service UUID of the BM78xBT (advertised by some meters).
PRIMARY_SERVICE_UUID = "0003cdd0-0000-1000-8000-00805f9b0131"

# Manufacturer-specific data carried in the advertisement (spec bytes [14..19]):
# company ID 0x0131, then b'B','M', model-series (0x0B = BM78x), status.
_MANUFACTURER_ID = 0x0131
_MODEL_SERIES_ID = 0x0B


@dataclass(frozen=True)
class DiscoveredMeter:
    """A BM78xBT meter found during a scan."""

    address: str
    name: Optional[str]
    rssi: Optional[int]
    model_series_id: int = _MODEL_SERIES_ID


def is_brymenble_advertisement(adv: AdvertisementData) -> bool:
    """Return True if an advertisement belongs to a BM78xBT meter.

    Matches the primary service UUID, or the fixed manufacturer-data pattern
    (company ``0x0131``, payload ``b'BM'`` + model-series ``0x0B``).
    """
    if PRIMARY_SERVICE_UUID in [u.lower() for u in (adv.service_uuids or [])]:
        return True
    mfr = (adv.manufacturer_data or {}).get(_MANUFACTURER_ID)
    return (
        mfr is not None
        and len(mfr) >= 3
        and mfr[:2] == b"BM"
        and mfr[2] == _MODEL_SERIES_ID
    )


async def find_meters(
    timeout: float = 5.0,
    scanner_factory: Callable[..., object] = BleakScanner,
) -> List[DiscoveredMeter]:
    """Scan for BM78xBT meters for ``timeout`` seconds and return them.

    ``scanner_factory`` is a test seam (defaults to ``bleak.BleakScanner``).
    """
    found = {}

    def _handler(device: BLEDevice, adv: AdvertisementData) -> None:
        if is_brymenble_advertisement(adv):
            found[device.address] = DiscoveredMeter(
                address=device.address,
                name=adv.local_name or device.name,
                rssi=adv.rssi,   # bleak exposes RSSI on the advertisement
            )

    async with scanner_factory(detection_callback=_handler):
        await asyncio.sleep(timeout)
    return list(found.values())


async def find_first_meter(
    timeout: float = 5.0,
    retry_interval: float = 10.0,
    on_retry: Optional[Callable[[int], None]] = None,
    scanner_factory: Callable[..., object] = BleakScanner,
) -> Optional[DiscoveredMeter]:
    """Scan until a BM78xBT meter is found, then return it (or ``None``).

    Long-running consumers (overlay, bridge, connection-state tool) all used
    to hand-roll this "scan, wait, retry" loop; this helper is the shared
    version. ``retry_interval`` is the gap between scans (set ``<= 0`` for a
    single-shot scan that returns ``None`` when nothing is found).
    ``on_retry``, if given, is called as ``on_retry(attempt)`` before each
    re-scan so callers can log progress. ``scanner_factory`` is the same test
    seam as ``find_meters``.
    """
    attempt = 0
    while True:
        attempt += 1
        meters = await find_meters(timeout=timeout, scanner_factory=scanner_factory)
        if meters:
            return meters[0]
        if retry_interval <= 0:
            return None
        if on_retry is not None:
            on_retry(attempt)
        await asyncio.sleep(retry_interval)
