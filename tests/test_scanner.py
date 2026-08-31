"""Tests for BM78xBT discovery (brymenble.scanner)."""
import asyncio
from types import SimpleNamespace

from brymenble.scanner import find_first_meter, find_meters, is_brymenble_advertisement

_MFR = 0x0131


def _adv(service_uuids=None, manufacturer_data=None, local_name=None, rssi=None):
    return SimpleNamespace(
        service_uuids=service_uuids or [],
        manufacturer_data=manufacturer_data or {},
        local_name=local_name,
        rssi=rssi,
    )


def test_match_manufacturer_data():
    adv = _adv(manufacturer_data={_MFR: b"BM\x0b\x00"})
    assert is_brymenble_advertisement(adv)


def test_match_service_uuid():
    adv = _adv(service_uuids=["0003CDD0-0000-1000-8000-00805F9B0131"])
    assert is_brymenble_advertisement(adv)


def test_no_match_empty():
    assert not is_brymenble_advertisement(_adv())


def test_no_match_wrong_company():
    adv = _adv(manufacturer_data={0xFFFF: b"BM\x0b\x00"})
    assert not is_brymenble_advertisement(adv)


def test_no_match_wrong_signature():
    # Right company id but not the 'BM' + 0x0B pattern.
    adv = _adv(manufacturer_data={_MFR: b"XX\x0b\x00"})
    assert not is_brymenble_advertisement(adv)


def test_find_meters():
    class FakeScanner:
        def __init__(self, detection_callback):
            self.cb = detection_callback

        async def __aenter__(self):
            self.cb(
                SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="BM78xBT"),
                _adv(manufacturer_data={_MFR: b"BM\x0b\x00"},
                     local_name="BM78xBT", rssi=-50),
            )
            return self

        async def __aexit__(self, *a):
            return None

    async def _run():
        meters, seen = await find_meters(timeout=0.05, scanner_factory=FakeScanner)
        assert len(meters) == 1
        m = meters[0]
        assert m.address == "AA:BB:CC:DD:EE:FF"
        assert m.name == "BM78xBT"
        assert m.rssi == -50
        assert m.model_series_id == 0x0B
        # The diagnostic summary captured the advertisement.
        assert len(seen) == 1
        assert "AA:BB:CC:DD:EE:FF" in seen[0]

    asyncio.run(_run())


def test_find_first_meter_single_shot_returns_first():
    class FakeScanner:
        def __init__(self, detection_callback):
            self.cb = detection_callback

        async def __aenter__(self):
            self.cb(
                SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="BM78xBT"),
                _adv(manufacturer_data={_MFR: b"BM\x0b\x00"}, local_name="BM78xBT"),
            )
            return self

        async def __aexit__(self, *a):
            return None

    async def _run():
        m = await find_first_meter(
            timeout=0.05, retry_interval=0, scanner_factory=FakeScanner
        )
        assert m is not None
        assert m.address == "AA:BB:CC:DD:EE:FF"

    asyncio.run(_run())


def test_find_first_meter_single_shot_none_when_empty():
    class FakeScanner:
        def __init__(self, detection_callback):
            self.cb = detection_callback

        async def __aenter__(self):
            return self   # no advertisement -> no meter

        async def __aexit__(self, *a):
            return None

    async def _run():
        m = await find_first_meter(
            timeout=0.01, retry_interval=0, scanner_factory=FakeScanner
        )
        assert m is None

    asyncio.run(_run())


def test_find_first_meter_retries_until_found():
    scans = {"n": 0}
    retried: list = []

    class FakeScanner:
        def __init__(self, detection_callback):
            self.cb = detection_callback

        async def __aenter__(self):
            scans["n"] += 1
            if scans["n"] == 1:
                return self   # first scan finds nothing
            self.cb(
                SimpleNamespace(address="AA:BB:CC:DD:EE:FF", name="BM78xBT"),
                _adv(manufacturer_data={_MFR: b"BM\x0b\x00"}, local_name="BM78xBT"),
            )
            return self

        async def __aexit__(self, *a):
            return None

    async def _run():
        m = await find_first_meter(
            timeout=0.01,
            retry_interval=0.01,
            scanner_factory=FakeScanner,
            on_retry=lambda attempt: retried.append(attempt),
        )
        assert m is not None
        assert m.address == "AA:BB:CC:DD:EE:FF"

    asyncio.run(_run())
    assert scans["n"] == 2
    assert retried == [1]
