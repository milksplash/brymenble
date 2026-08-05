"""Tests for BM78xBT discovery (brymen.scanner)."""
import asyncio
from types import SimpleNamespace

from brymen.scanner import find_meters, is_brymen_advertisement

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
    assert is_brymen_advertisement(adv)


def test_match_service_uuid():
    adv = _adv(service_uuids=["0003CDD0-0000-1000-8000-00805F9B0131"])
    assert is_brymen_advertisement(adv)


def test_no_match_empty():
    assert not is_brymen_advertisement(_adv())


def test_no_match_wrong_company():
    adv = _adv(manufacturer_data={0xFFFF: b"BM\x0b\x00"})
    assert not is_brymen_advertisement(adv)


def test_no_match_wrong_signature():
    # Right company id but not the 'BM' + 0x0B pattern.
    adv = _adv(manufacturer_data={_MFR: b"XX\x0b\x00"})
    assert not is_brymen_advertisement(adv)


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
        meters = await find_meters(timeout=0.05, scanner_factory=FakeScanner)
        assert len(meters) == 1
        m = meters[0]
        assert m.address == "AA:BB:CC:DD:EE:FF"
        assert m.name == "BM78xBT"
        assert m.rssi == -50
        assert m.model_series_id == 0x0B

    asyncio.run(_run())
