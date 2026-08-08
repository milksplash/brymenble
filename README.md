# brymenble

> **⚠️ Unofficial.** This is an independent, community-developed SDK. It is
> **not affiliated with, endorsed by, or sponsored by** Brymen Technology Corporation. "Brymen" and the device model names are trademarks of their
> respective owners.

Open-source Python SDK for the **Brymen BM78xBT** Bluetooth Low Energy
multimeter. This is the monorepo for both the SDK itself (`src/brymen/`) and a
sample console app (`examples/`) that displays the meter output.

> **⚠️ Data source.** The SDK reads the meter's **official wireless data
> protocol** over BLE — the numeric value, units, and status flags the meter
> transmits. It does **not** read, capture, or analyze the meter's physical
> display; anything rendered from this data is an emulation, not a video feed.

## SDK

The SDK is a pip-installable package that handles the whole protocol:

- `brymen.constants` — protocol constants and lookup tables
- `brymen.crc` — CRC-16 (poly 0xA001) used by the protocol
- `brymen.commands` — building command packets (auth, etc.)
- `brymen.parsers` — turning raw packets/frames into `InfoPacket`, `ReadingPacket`, `RtcTime`
- `brymen.formatter` — converting a parsed reading into a display string (`"123.45 V"`)
- `brymen.transport` — `BrymenClient`: connect, authenticate, subscribe, stream parsed frames, plus a retry/reconnect policy (`ensure_connected`) and idempotent `close()`

### Documentation

- `docs/SDK_DATA_REFERENCE.md` — reference of every parsed field the SDK exposes (`ReadingPacket`, `InfoPacket`, `RtcTime`, `CommandResponse`)

The official BM78xBT protocol specification is maintained locally only and is
not distributed with this repository.

### Install

```bash
pip install -e .          # from the repo root (installs `brymenble` + `bleak`)
```

### Minimal use

```python
import asyncio
from brymen import BrymenClient, DEFAULT_PASSWORD, find_meters, format_reading

async def main():
    meters = await find_meters()
    if not meters:
        print("No BM78xBT meters found.")
        return
    mac = meters[0].address

    async with BrymenClient(mac, DEFAULT_PASSWORD, sync_rtc_on_connect=True) as client:
        async for frame in client:
            print(frame.info.mac_str, format_reading(frame.readings[0]))

asyncio.run(main())
```

## Sample console app

`examples/console.py` is a thin program built on the SDK: it connects to a
meter and prints its readings as they arrive. With no MAC given it scans for
the first BM78xBT meter it finds.

```bash
python examples/console.py [MAC] [PASSWORD]
```

For on-demand reads and hardware probing, see `tools/probe.py` (exercises the
command/response layer against a real meter) and `tools/capture.py` (records
real frames for the test fixtures).

## Platform support

Linux and Windows are supported. macOS randomizes BLE device MAC addresses, so the SDK's discovery flow
(`find_meters()` returning an address, then connecting to it with
`BrymenClient`) does not work reliably there.

## Tests

Offline tests (no meter required):

```bash
.venv\Scripts\python.exe -m pytest
```

`tools/capture.py` captures real frames from a meter into
`tests/fixtures/captures.json`. That file is gitignored and kept local only —
real frames embed the meter's MAC address, so it must not be committed.

## License

MIT — see [LICENSE](LICENSE).

"Brymen" and the device model names are trademarks of their respective owners;
this project is not affiliated with or endorsed by Brymen Technology Corporation