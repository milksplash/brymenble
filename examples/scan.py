"""Scan for Brymen BM78xBT meters over BLE and print what's found.

Usage:
    python examples/scan.py             # scan for 5s, print BM78xBT meters
    python examples/scan.py 10          # scan for 10s
    python examples/scan.py --raw 10    # dump ALL advertisements (debugging)
"""
import asyncio
import sys

from bleak import BleakScanner

from brymen import find_meters


def _fmt_manufacturer_data(mfr):
    if not mfr:
        return ""
    return " " + " ".join(f"{cid:04x}:{payload.hex()}" for cid, payload in sorted(mfr.items()))


async def scan_raw(timeout: float) -> None:
    """Print every advertisement seen (to verify the BM78xBT fingerprint)."""
    print(f"Scanning for ALL BLE advertisements ({timeout:.0f}s)...")
    seen = set()

    def _cb(device, adv):
        if device.address in seen:
            return
        seen.add(device.address)
        uuids = ",".join(adv.service_uuids) if adv.service_uuids else "-"
        print(f"  {device.address}  name={adv.local_name!r}  rssi={adv.rssi}")
        print(f"      service_uuids: {uuids}")
        print(f"      manufacturer_data:{_fmt_manufacturer_data(adv.manufacturer_data)}")

    async with BleakScanner(detection_callback=_cb):
        await asyncio.sleep(timeout)
    print(f"Seen {len(seen)} unique device(s).")


async def main(timeout: float) -> None:
    print(f"Scanning for Brymen BM78xBT meters ({timeout:.0f}s)...")
    meters = await find_meters(timeout=timeout)
    if not meters:
        print("No BM78xBT meters found. Try '--raw' to see all advertisements.")
        return
    print(f"Found {len(meters)} meter(s):")
    for m in meters:
        name = m.name or "(no name)"
        rssi = f"{m.rssi} dBm" if m.rssi is not None else "n/a"
        print(f"  {m.address}  {name}  {rssi}  series=0x{m.model_series_id:02X}")


if __name__ == "__main__":
    args = sys.argv[1:]
    raw = "--raw" in args
    timeout = 5.0
    for a in args:
        if a != "--raw":
            timeout = float(a)
    try:
        if raw:
            asyncio.run(scan_raw(timeout))
        else:
            asyncio.run(main(timeout))
    except KeyboardInterrupt:
        print("\nScan aborted.")
